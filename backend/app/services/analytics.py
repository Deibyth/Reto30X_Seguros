"""Analytics service — pandas + raw SQL for dashboard data."""

import logging
import math
from collections import Counter

import pandas as pd
from sqlalchemy import text

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Dashboard analytics using pandas aggregation over raw SQL queries."""

    def __init__(self, session_maker):
        self._session_maker = session_maker

    async def _fetch_df(self, sql: str) -> pd.DataFrame:
        async with self._session_maker() as session:
            conn = await session.connection()
            df = await conn.run_sync(
                lambda sync_conn: pd.read_sql(text(sql), sync_conn)
            )
        return df

    async def _fetch_one(self, sql: str) -> tuple | None:
        async with self._session_maker() as session:
            result = await session.execute(text(sql))
            return result.first()

    async def get_pipeline_summary(self) -> dict:
        row = await self._fetch_one(
            "SELECT "
            "  COUNT(*) as total, "
            "  SUM(CASE WHEN activa = 1 THEN 1 ELSE 0 END) as active, "
            "  SUM(CASE WHEN estado_actual = 'completado' THEN 1 ELSE 0 END) as completed "
            "FROM sessions"
        )
        total_sessions = row[0] or 0 if row else 0
        active_sessions = row[1] or 0 if row else 0
        completed_sessions = row[2] or 0 if row else 0

        apps_row = await self._fetch_one("SELECT COUNT(*) FROM applications")
        total_applications = apps_row[0] if apps_row else 0

        apps_df = await self._fetch_df(
            "SELECT estado, COUNT(*) as count FROM applications GROUP BY estado"
        )
        applications_by_status = {}
        if not apps_df.empty:
            applications_by_status = dict(
                zip(apps_df["estado"], apps_df["count"].astype(int))
            )

        conversion_rate = 0.0
        if total_sessions > 0:
            conversion_rate = round(total_applications / total_sessions * 100, 2)

        abandon_df = await self._fetch_df(
            "SELECT estado_actual, COUNT(*) as count FROM sessions "
            "WHERE estado_actual != 'completado' "
            "GROUP BY estado_actual ORDER BY count DESC"
        )
        abandon_at_section = []
        if not abandon_df.empty:
            abandon_at_section = [
                {"section": row["estado_actual"], "count": int(row["count"])}
                for _, row in abandon_df.iterrows()
            ]

        return {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "completed_sessions": completed_sessions,
            "total_applications": total_applications,
            "applications_by_status": applications_by_status,
            "conversion_rate": conversion_rate,
            "abandon_at_section": abandon_at_section,
        }

    async def get_daily_trends(self, days: int = 30) -> list[dict]:
        df = await self._fetch_df(
            "SELECT DATE(created_at) as date, "
            "COUNT(*) as applications, "
            "SUM(CASE WHEN estado = 'completada' THEN 1 ELSE 0 END) as completions "
            "FROM applications "
            f"WHERE created_at >= DATE('now', '-{days} days') "
            "GROUP BY DATE(created_at) ORDER BY date"
        )
        if df.empty:
            return []
        return df.fillna(0).to_dict(orient="records")

    async def get_customer_profile(self) -> dict:
        salary_df = await self._fetch_df(
            "SELECT "
            "  CASE "
            "    WHEN salario IS NULL THEN 'Sin dato'"
            "    WHEN salario < 1000000 THEN '$0-$1M'"
            "    WHEN salario < 2000000 THEN '$1M-$2M'"
            "    WHEN salario < 3000000 THEN '$2M-$3M'"
            "    WHEN salario < 4000000 THEN '$3M-$4M'"
            "    WHEN salario < 5000000 THEN '$4M-$5M'"
            "    ELSE '$5M+'"
            "  END as range,"
            "  COUNT(*) as count "
            "FROM customers "
            "GROUP BY range ORDER BY MIN(salario)"
        )
        salary_distribution = []
        if not salary_df.empty:
            salary_distribution = [
                {"range": row["range"], "count": int(row["count"])}
                for _, row in salary_df.iterrows()
            ]

        contract_df = await self._fetch_df(
            "SELECT COALESCE(tipo_contrato, 'Sin dato') as type, "
            "COUNT(*) as count "
            "FROM customers GROUP BY tipo_contrato ORDER BY count DESC"
        )
        contract_types = []
        if not contract_df.empty:
            contract_types = [
                {"type": row["type"], "count": int(row["count"])}
                for _, row in contract_df.iterrows()
            ]

        stats_row = await self._fetch_one(
            "SELECT "
            "  AVG(antiguedad_meses) as avg_tenure, "
            "  AVG(score_crediticio) as avg_score, "
            "  COUNT(*) as total "
            "FROM customers"
        )
        avg_tenure = round(stats_row[0], 2) if stats_row and stats_row[0] else 0.0
        avg_score = round(stats_row[1], 2) if stats_row and stats_row[1] else 0.0
        total_customers = stats_row[2] if stats_row else 0

        return {
            "salary_distribution": salary_distribution,
            "contract_types": contract_types,
            "avg_tenure_months": avg_tenure,
            "avg_credit_score": avg_score,
            "total_customers": total_customers,
        }

    async def get_credit_stats(self) -> dict:
        df = await self._fetch_df(
            "SELECT monto_solicitado, plazo_meses, "
            "COALESCE(destino, 'Sin dato') as destino "
            "FROM credits"
        )
        if df.empty:
            return {
                "avg_amount": 0.0,
                "avg_term_months": 0.0,
                "destino_distribution": [],
                "amount_ranges": [],
                "total_credits": 0,
                "total_volume": 0.0,
            }

        avg_amount = round(float(df["monto_solicitado"].mean()), 2)
        avg_term = round(float(df["plazo_meses"].mean()), 2)
        total_credits = len(df)
        total_volume = round(float(df["monto_solicitado"].sum()), 2)

        dest_counts = df["destino"].value_counts()
        destino_distribution = [
            {"destino": dest, "count": int(count)}
            for dest, count in dest_counts.items()
        ]

        bins = [0, 5_000_000, 10_000_000, 15_000_000, 20_000_000, float("inf")]
        labels = ["$0-$5M", "$5M-$10M", "$10M-$15M", "$15M-$20M", "$20M+"]
        df["amount_range"] = pd.cut(
            df["monto_solicitado"], bins=bins, labels=labels, right=False
        )
        range_counts = df["amount_range"].value_counts().sort_index()
        amount_ranges = [
            {"range": str(rng), "count": int(count)}
            for rng, count in range_counts.items()
        ]

        return {
            "avg_amount": avg_amount,
            "avg_term_months": avg_term,
            "destino_distribution": destino_distribution,
            "amount_ranges": amount_ranges,
            "total_credits": total_credits,
            "total_volume": total_volume,
        }

    async def get_ai_efficiency(self) -> dict:
        msg_row = await self._fetch_one(
            "SELECT AVG(msg_count) FROM ("
            "  SELECT s.id, COUNT(c.id) as msg_count"
            "  FROM sessions s"
            "  JOIN conversations c ON c.session_id = s.id"
            "  WHERE s.estado_actual = 'completado'"
            "  GROUP BY s.id"
            ")"
        )
        avg_messages = round(msg_row[0], 2) if msg_row and msg_row[0] else 0.0

        conv_row = await self._fetch_one("SELECT COUNT(*) FROM conversations")
        total_conversations = conv_row[0] if conv_row else 0

        sessions_df = await self._fetch_df(
            "SELECT campos_diligenciados FROM sessions "
            "WHERE estado_actual = 'completado'"
        )
        field_counts = []
        all_field_presence = Counter()
        session_count = 0
        if not sessions_df.empty:
            for _, row in sessions_df.iterrows():
                cd = row.get("campos_diligenciados")
                if isinstance(cd, dict):
                    field_counts.append(len(cd))
                    for key in cd:
                        all_field_presence[key] += 1
                    session_count += 1

        avg_fields_collected = 0.0
        if field_counts:
            avg_fields_collected = round(sum(field_counts) / len(field_counts), 2)

        total_sessions_with_data = session_count
        top_omitted = []
        if all_field_presence and total_sessions_with_data > 0:
            omitted = sorted(
                all_field_presence.items(), key=lambda x: (x[1], x[0])
            )
            top_omitted = [
                {"field": field, "count": total_sessions_with_data - count}
                for field, count in omitted[:10]
            ]

        error_df = await self._fetch_df(
            "SELECT COUNT(DISTINCT session_id) as cnt "
            "FROM conversations "
            "WHERE metadata_json IS NOT NULL "
            "AND json_extract(metadata_json, '$.error') IS NOT NULL"
        )
        sessions_with_tool_errors = 0
        if not error_df.empty:
            sessions_with_tool_errors = int(error_df.iloc[0]["cnt"])

        return {
            "avg_messages_per_completed_session": avg_messages,
            "total_conversations": total_conversations,
            "avg_fields_collected": avg_fields_collected,
            "top_omitted_fields": top_omitted,
            "sessions_with_tool_errors": sessions_with_tool_errors,
        }

    async def get_insurance(self) -> dict:
        df = await self._fetch_df(
            "SELECT p.estado, p.prima, i.nombre as tipo_seguro "
            "FROM policies p "
            "JOIN insurances i ON i.id = p.insurance_id"
        )
        if df.empty:
            return {
                "total_policies": 0,
                "active_policies": 0,
                "by_type": [],
                "by_status": [],
                "total_premiums": 0.0,
                "claims_stats": {"total": 0, "approved": 0, "total_amount": 0.0},
            }

        total_policies = len(df)
        active_policies = int((df["estado"] == "activo").sum())
        total_premiums = round(float(df["prima"].sum()), 2)

        by_type = (
            df.groupby("tipo_seguro")
            .agg(count=("estado", "count"), premiums=("prima", "sum"))
            .reset_index()
        )
        by_type = [
            {
                "tipo": row["tipo_seguro"],
                "count": int(row["count"]),
                "premiums": round(float(row["premiums"]), 2),
            }
            for _, row in by_type.iterrows()
        ]

        by_status = (
            df.groupby("estado")
            .agg(count=("estado", "count"))
            .reset_index()
        )
        by_status = [
            {"estado": row["estado"], "count": int(row["count"])}
            for _, row in by_status.iterrows()
        ]

        claims_df = await self._fetch_df(
            "SELECT estado, monto_reclamado FROM claims"
        )
        claims_stats = {"total": 0, "approved": 0, "total_amount": 0.0}
        if not claims_df.empty:
            claims_stats["total"] = len(claims_df)
            claims_stats["approved"] = int((claims_df["estado"] == "aprobado").sum())
            claims_stats["total_amount"] = round(
                float(claims_df["monto_reclamado"].sum()), 2
            )

        return {
            "total_policies": total_policies,
            "active_policies": active_policies,
            "by_type": by_type,
            "by_status": by_status,
            "total_premiums": total_premiums,
            "claims_stats": claims_stats,
        }

    async def get_supervision(self) -> list[dict]:
        """Return all sessions with conversations for human-in-the-loop monitoring."""
        sessions_df = await self._fetch_df(
            "SELECT s.id, s.customer_id, s.estado_actual, s.ultima_intencion, "
            "s.insurance_profile, s.campos_diligenciados, s.created_at, s.updated_at "
            "FROM sessions s ORDER BY s.updated_at DESC"
        )
        if sessions_df.empty:
            return []

        # Get customer names
        customer_ids = sessions_df["customer_id"].dropna().unique().tolist()
        customer_map: dict[str, str] = {}
        if customer_ids:
            ids_str = ",".join(f"'{cid}'" for cid in customer_ids)
            cust_df = await self._fetch_df(
                f"SELECT id, nombre_completo FROM customers WHERE id IN ({ids_str})"
            )
            if not cust_df.empty:
                customer_map = dict(zip(cust_df["id"], cust_df["nombre_completo"]))

        # Get conversation counts per session
        conv_count_df = await self._fetch_df(
            "SELECT session_id, COUNT(*) as cnt FROM conversations GROUP BY session_id"
        )
        conv_counts: dict[str, int] = {}
        if not conv_count_df.empty:
            conv_counts = dict(
                zip(conv_count_df["session_id"], conv_count_df["cnt"].astype(int))
            )

        # Get policy existence per session (policies reference customer_id)
        policy_df = await self._fetch_df(
            "SELECT DISTINCT customer_id FROM policies"
        )
        policy_customers: set[str] = set()
        if not policy_df.empty:
            policy_customers = set(policy_df["customer_id"])

        # Get last 5 conversations for each session
        conv_df = await self._fetch_df(
            "SELECT session_id, rol, mensaje, created_at FROM conversations "
            "ORDER BY session_id, created_at"
        )

        # Group conversations by session_id and take last 5
        conv_groups: dict[str, list[dict]] = {}
        if not conv_df.empty:
            for _, row in conv_df.iterrows():
                sid = str(row["session_id"])
                if sid not in conv_groups:
                    conv_groups[sid] = []
                msg = row.get("mensaje", "") or ""
                conv_groups[sid].append({
                    "rol": row["rol"],
                    "mensaje": msg[:200],
                    "created_at": row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
                })

        def _safe(val, default=None):
            """Convert NaN/None to default, otherwise return str(val)."""
            if val is None or (isinstance(val, float) and math.isnan(val)):
                return default
            return val

        result: list[dict] = []
        for _, row in sessions_df.iterrows():
            sid = str(row["id"])
            cust_id = str(row["customer_id"]) if row["customer_id"] and not (isinstance(row["customer_id"], float) and math.isnan(row["customer_id"])) else None
            insurance_profile = row.get("insurance_profile")
            product_context = None
            if isinstance(insurance_profile, dict):
                product_context = insurance_profile.get("product_context")

            session_convs = conv_groups.get(sid, [])
            created_at = row.get("created_at")
            updated_at = row.get("updated_at")
            result.append({
                "id": sid,
                "customer_id": cust_id,
                "customer_name": customer_map.get(cust_id) if cust_id else None,
                "estado_actual": _safe(row.get("estado_actual"), ""),
                "product_context": _safe(product_context),
                "ultima_intencion": _safe(row.get("ultima_intencion")),
                "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at) if created_at else "",
                "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else str(updated_at) if updated_at else "",
                "conversations": session_convs[-5:],
                "total_messages": conv_counts.get(sid, 0),
                "has_policy": cust_id in policy_customers if cust_id else False,
            })

        return result

    async def get_full_summary(self) -> dict:
        pipeline = await self.get_pipeline_summary()
        trends = await self.get_daily_trends()
        customers = await self.get_customer_profile()
        credits = await self.get_credit_stats()
        efficiency = await self.get_ai_efficiency()

        return {
            "pipeline": pipeline,
            "trends": trends,
            "customers": customers,
            "credits": credits,
            "efficiency": efficiency,
        }

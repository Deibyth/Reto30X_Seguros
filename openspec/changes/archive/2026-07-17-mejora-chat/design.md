# Design: Mejora Chat — Categorías de Afiliación y Tasas Diferenciales

## Technical Approach

Add `categoria_afiliacion` (A/B/C) to Customer with auto-calculation from salary, create an `InterestRate` model with rates per category+product+modalidad, update `simulate_credit` to use differential rates, and inject a CATEGORÍAS Y TASAS section into Anna's system prompt. Persist new table and column via `Base.metadata.create_all()` (Alembic not configured).

## Architecture Decisions

| Decision | Options | Choice | Rationale |
|----------|---------|--------|-----------|
| InterestRate.modalidad_pago | Omit / add nullable column | **Add optional `modalidad_pago`** | Libre Inversión and Compra de Cartera have different rates per modalidad (libranza vs pago directo) — without this column, the unique constraint `(categoria, product_id, vigencia_desde)` prevents storing both rates |
| Unique constraint | Without modalidad / with modalidad | **(categoria, product_id, modalidad_pago, vigencia_desde)** | Allows two InterestRate rows for same product+category (libranza vs directo) while preventing true duplicates |
| Category auto-calculation trigger | On model `__init__` / before insert in seed + tool | **In `_calcular_categoria()` called from domain_tools on customer creation, and seed sets it directly** | ORM auto-calculation in `__init__` conflates concerns — domain_tools and seed are the two insertion paths; hooking both keeps logic explicit |
| Rate lookup fallback | Flat 18% / per-product defaults | **Per-product fallback: 18% consumo, 10.7% hipotecario, 12% educativo** | More realistic than flat 18%; mirrors actual Colsubsidio rate structure |
| Migration strategy | Alembic / create_all on startup | **`Base.metadata.create_all()`** | Follows existing project convention (data-models spec F-DATA-06); new column is nullable, no data migration |
| `simulate_credit` parameter | `customer_id` only / `customer_id + categoria` | **Both: `customer_id` (lookup) or `categoria` (explicit override)** | Enables simulation for anonymous users or manual category override |

## Data Flow

```
User: "¿qué tasa me corresponde?"
  ──→ Anna reads system prompt (CATEGORÍAS Y TASAS section)
  ──→ Calls get_customer(documento) → incluye categoria_afiliacion
  ──→ Calls simulate_credit(monto, plazo, customer_id)
       │
       ├── customer_id → lookup Customer.categoria_afiliacion
       │   (calc via _calcular_categoria if null)
       ├── query InterestRate WHERE categoria + product_id + modalidad_pago
       │   ORDER BY vigencia_desde DESC LIMIT 1
       ├── fallback per product type if no InterestRate row
       └── French amortization: cuota = P[r(1+r)^n]/[(1+r)^n-1]
            r = tasa_anual / 12
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/app/models/interest_rate.py` | Create | `InterestRate` ORM: id, categoria (CHECK A/B/C), product_id (FK), tasa_min, tasa_max, vigencia_desde, modalidad_pago (nullable), activo, created_at, updated_at. Unique: (categoria, product_id, modalidad_pago, vigencia_desde) |
| `backend/app/models/customer.py` | Modify | Add `categoria_afiliacion: String(1), nullable=True`, with CHECK IN ('A','B','C') |
| `backend/app/models/__init__.py` | Modify | Import InterestRate, add to `__all__` |
| `backend/app/tools/domain_tools.py` | Modify | Add `_calcular_categoria()`; update `simulate_credit` signature + rate lookup; update `get_customer` output; update `create_application` for modalidad_pago |
| `backend/app/services/chat.py` | Modify | Append CATEGORÍAS Y TASAS section + modalidad_pago instructions in `_build_system_prompt()` |
| `backend/app/schemas/credit_form.py` | Modify | Add `categoria_afiliacion` (select, opt) and `modalidad_pago` (select, opt, ["libranza","pago_directo"]) to FormSchema |
| `backend/app/seed.py` | Modify | Set `categoria_afiliacion` on seed customers; insert 24+ InterestRate rows per tasa table |

## Interfaces

### `InterestRate` model

```python
class InterestRate(Base):
    __tablename__ = "interest_rates"
    __table_args__ = (
        UniqueConstraint("categoria", "product_id", "modalidad_pago", "vigencia_desde"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    categoria: Mapped[str] = mapped_column(String(1), CheckConstraint("categoria IN ('A','B','C')"), nullable=False)
    product_id: Mapped[str] = mapped_column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    tasa_min: Mapped[float] = mapped_column(Float, nullable=False)
    tasa_max: Mapped[float] = mapped_column(Float, nullable=False)
    modalidad_pago: Mapped[str | None] = mapped_column(String(50), nullable=True)  # "libranza" | "pago_directo" | None
    vigencia_desde: Mapped[date] = mapped_column(Date, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
```

### `_calcular_categoria`

```python
SMMLV_2026 = 1_750_905

def _calcular_categoria(salario: int | None) -> str:
    if not salario or salario <= 0:
        return "A"
    if salario <= 2 * SMMLV_2026:   # $3.501.810
        return "A"
    if salario <= 4 * SMMLV_2026:   # $7.003.620
        return "B"
    return "C"
```

### `simulate_credit` new signature

```python
async def simulate_credit(
    monto: float,
    plazo: int,
    customer_id: str | None = None,
    categoria: str | None = None,
    modalidad: str = "libranza",
) -> str
```

### Rate lookup logic

```python
# Query InterestRate by categoria + product_id + modalidad_pago match
stmt = (
    select(InterestRate)
    .where(
        InterestRate.categoria == categoria,
        InterestRate.product_id == product_id,
        InterestRate.activo == True,
        or_(
            InterestRate.modalidad_pago == modalidad,
            InterestRate.modalidad_pago.is_(None),
        ),
    )
    .order_by(InterestRate.vigencia_desde.desc())
    .limit(1)
)
```

## Seed Data

InterestRate rows per product × category (24 minimum):

| Categoría | Producto | Modalidad | A | B | C |
|-----------|----------|-----------|---|---|---|
| Libre Inversión | Crédito Libre Inversión | libranza | 12 | 15 | 18 |
| Libre Inversión | Crédito Libre Inversión | pago_directo | 15 | 18 | 22 |
| Compra Cartera | Compra de Cartera | libranza | 12 | 15 | 18 |
| Compra Cartera | Compra de Cartera | pago_directo | 15 | 18 | 22 |
| Mujeres | Crédito para Mujeres | NULL | 12 | 15 | 18 |
| Educativo | Crédito Educativo | NULL | 10 | 13 | 16 |
| Hipotecario | Crédito Hipotecario | NULL | 10.7 | 10.7 | 10.7 |
| Cupo | Cupo de Crédito | NULL | 18 | 22 | 26 |
| Microcrédito | Microcrédito | NULL | 20 | 24 | 28 |

(21 rows = 9 entries × 3 categories, where Libre Inversión and Compra de Cartera count as 2 entries each = 7 product groups → 9 logical entries). Plus 3 fallback defaults (one per category, tasa=18%, sin producto).

Customer: Juan Pérez (sal $3.5M → cat A), Pedro Jiménez (sal $0 → cat A).

## Migration Strategy

- **Up**: Add nullable column to customers → no existing data affected. Create interest_rates table via `Base.metadata.create_all()` (runs on startup). Updated seed populates both.
- **Rollback**: Drop `categoria_afiliacion` column, drop `interest_rates` table, revert domain_tools + chat.py + credit_form.py + seed.py.

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Product names in InterestRate seed don't match actual Product.nombre | Low | Use product_map from seed.py — insert by name first, then query for FK |
| `modalidad_pago` column addition makes model diverge from original proposal | Medium | Documented decision — necessary for correct rate discrimination |

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | `_calcular_categoria` thresholds | Pure function: 0→A, $3.5M→A, $3.5M+1→B, $7M→B, $7M+1→C |
| Unit | `simulate_credit` amortization | Known inputs + expected cuota (compare with reference calc) |
| Integration | Rate lookup with InterestRate | Seed 3 rows, query by categoria+product, assert correct rate |
| Integration | `create_application` with modalidad_pago | Assert Credit.modalidad_pago set from form_data |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

import { useRef, useState, useEffect, useCallback } from "react";
import { useMutation } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { Loader2, Send, AlertCircle, MessageSquare } from "lucide-react";
import { ApiClient, type ChatResponse } from "@/lib/api";

const api = new ApiClient();

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface ButtonDef {
  label: string;
  value: string;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  buttons?: ButtonDef[];
}

/* ------------------------------------------------------------------ */
/*  Tangram decoration — formas geométricas decorativas                */
/* ------------------------------------------------------------------ */

function TangramDecorations() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      {/* Triángulo grande — esquina superior derecha */}
      <svg
        className="absolute -right-16 -top-16 h-48 w-48 text-colsubsidio-yellow/10"
        viewBox="0 0 100 100"
        fill="currentColor"
      >
        <polygon points="0,0 100,0 100,100" />
      </svg>
      {/* Cuadrado — esquina inferior izquierda */}
      <svg
        className="absolute -bottom-12 -left-12 h-28 w-28 text-colsubsidio-blue/8"
        viewBox="0 0 100 100"
        fill="currentColor"
      >
        <rect x="10" y="10" width="80" height="80" />
      </svg>
      {/* Triángulo pequeño — esquina inferior derecha */}
      <svg
        className="absolute -bottom-8 -right-8 h-20 w-20 text-colsubsidio-yellow/8"
        viewBox="0 0 100 100"
        fill="currentColor"
      >
        <polygon points="0,100 100,100 0,0" />
      </svg>
      {/* Paralelogramo — flotante lateral */}
      <svg
        className="absolute left-1/4 top-1/3 h-16 w-20 text-colsubsidio-blue/5 -translate-x-1/2"
        viewBox="0 0 100 80"
        fill="currentColor"
      >
        <polygon points="20,0 100,0 80,80 0,80" />
      </svg>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Typing Indicator — animated dots                                   */
/* ------------------------------------------------------------------ */

function TypingIndicator() {
  return (
    <div className="flex items-start gap-3 px-4 py-2">
      <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-colsubsidio-blue/10">
        <MessageSquare className="size-4 text-colsubsidio-blue" />
      </div>
      <div className="flex items-center gap-1 rounded-2xl bg-muted px-4 py-3">
        <span className="size-2 animate-bounce rounded-full bg-muted-foreground/60 [animation-delay:0ms]" />
        <span className="size-2 animate-bounce rounded-full bg-muted-foreground/60 [animation-delay:150ms]" />
        <span className="size-2 animate-bounce rounded-full bg-muted-foreground/60 [animation-delay:300ms]" />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Skeleton                                                           */
/* ------------------------------------------------------------------ */

function ChatSkeleton() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8">
      <div className="size-16 animate-pulse rounded-full bg-colsubsidio-blue/10" />
      <div className="h-4 w-48 animate-pulse rounded bg-colsubsidio-blue/10" />
      <div className="h-3 w-64 animate-pulse rounded bg-colsubsidio-blue/10" />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Auto-link content — converts URLs to clickable <a> tags           */
/* ------------------------------------------------------------------ */

const URL_REGEX = /(https?:\/\/[^\s<]+[^\s<.,;:!?])/g;

function AutoLinkContent({ text }: { text: string }) {
  if (!text) return null;
  const parts = text.split(URL_REGEX);
  return (
    <p className="whitespace-pre-wrap">
      {parts.map((part, i) =>
        URL_REGEX.test(part)
          ? <a key={i} href={part} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 text-colsubsidio-blue hover:text-colsubsidio-blue/80">{part}</a>
          : part,
      )}
    </p>
  );
}

/* ------------------------------------------------------------------ */
/*  Message Bubble                                                     */
/* ------------------------------------------------------------------ */

interface MessageBubbleProps {
  message: Message;
  index: number;
  onButtonClick: (value: string) => void;
}

function MessageBubble({ message, index, onButtonClick }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.25, delay: index * 0.04 }}
      className={`flex flex-col items-start gap-2 px-4 py-2 ${
        isUser ? "items-end" : ""
      }`}
    >
      <div className={`flex items-start gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
        {/* Avatar */}
        <div
          className={`flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
            isUser
              ? "bg-colsubsidio-blue text-white"
              : "bg-colsubsidio-yellow text-colsubsidio-dark"
          }`}
        >
          {isUser ? "T" : "PI"}
        </div>

        {/* Bubble */}
        <div
          className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
            isUser
              ? "bg-colsubsidio-blue text-white rounded-tr-md"
              : "bg-muted text-foreground rounded-tl-md"
          }`}
        >
          <AutoLinkContent text={message.content} />
        </div>
      </div>

      {/* Action buttons (assistant only) */}
      {!isUser && message.buttons && message.buttons.length > 0 && (
        <div className="flex flex-wrap gap-2 pl-11">
          {message.buttons.map((btn) => (
            <button
              key={btn.value}
              onClick={() => onButtonClick(btn.value)}
              className="rounded-full border border-colsubsidio-blue/30 bg-white px-4 py-1.5 text-sm font-medium text-colsubsidio-blue transition-all hover:bg-colsubsidio-blue hover:text-white"
            >
              {btn.label}
            </button>
          ))}
        </div>
      )}
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/*  ChatPanel                                                          */
/* ------------------------------------------------------------------ */

export function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const isAtBottomRef = useRef(true);
  const [hasInitialized, setHasInitialized] = useState(false);

  /* ---- Mutation ---- */
  const mutation = useMutation<ChatResponse, Error, string>({
    mutationFn: (message: string) => api.sendMessage(message),
    onSuccess: (data) => {
      setMessages((prev) => [
        ...prev,
        {
          id: `ai-${Date.now()}`,
          role: "assistant",
          content: data.reply,
          buttons: data.buttons,
        },
      ]);
    },
    onError: () => {
      // Error is shown via mutation.isError — no state change needed
    },
  });

  const isLoading = mutation.isPending;

  /* ---- check scroll position ---- */
  const handleScroll = useCallback(() => {
    const el = listRef.current;
    if (!el) return;
    const threshold = 40;
    isAtBottomRef.current =
      el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
  }, []);

  /* ---- auto-scroll ---- */
  useEffect(() => {
    if (isAtBottomRef.current) {
      listRef.current?.scrollTo({
        top: listRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages, isLoading]);

  /* ---- Mark as initialized after first render ---- */
  useEffect(() => {
    setHasInitialized(true);
  }, []);

  /* ---- Send handler ---- */
  const handleSend = useCallback(() => {
    const text = inputValue.trim();
    if (!text || mutation.isPending) return;

    // Optimistically add user message
    const userMsg: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInputValue("");
    mutation.mutate(text);
  }, [inputValue, mutation]);

  /* ---- Keyboard submit ---- */
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend],
  );

  /* ---- Retry ---- */
  const handleRetry = useCallback(() => {
    // Find the last user message and resend it
    const lastUserMsg = [...messages].reverse().find((m) => m.role === "user");
    if (lastUserMsg) {
      setMessages((prev) => prev.filter((m) => m.id !== "pending-error"));
      mutation.mutate(lastUserMsg.content);
    }
  }, [messages, mutation]);

  /* ---- Button click (sends button value as user message) ---- */
  const handleButtonClick = useCallback(
    (value: string) => {
      const userMsg: Message = {
        id: `user-${Date.now()}`,
        role: "user",
        content: value,
      };
      setMessages((prev) => [...prev, userMsg]);
      mutation.mutate(value);
    },
    [mutation],
  );

  /* ---- Reset error ---- */
  const handleDismissError = useCallback(() => {
    mutation.reset();
  }, [mutation]);

  /* ---- Render ---- */
  return (
    <div className="mx-auto flex h-[75vh] w-full flex-col md:max-w-[800px]">
      {/* Messages list */}
      <div
        ref={listRef}
        onScroll={handleScroll}
        className="relative flex-1 overflow-y-auto border rounded-t-xl bg-card py-4"
      >
        <TangramDecorations />

        <div className="relative z-10 space-y-1">
          {!hasInitialized ? (
            <ChatSkeleton />
          ) : messages.length === 0 && !isLoading ? (
            /* Empty state */
            <div className="flex h-full flex-col items-center justify-center gap-3 px-4 text-center">
              <div className="relative">
                <MessageSquare className="size-12 text-colsubsidio-blue/30" />
                {/* Mini tangram decorativo */}
                <svg
                  className="absolute -right-2 -top-2 h-5 w-5 text-colsubsidio-yellow/40"
                  viewBox="0 0 30 30"
                  fill="currentColor"
                >
                  <polygon points="0,30 30,30 15,0" />
                </svg>
              </div>
              <p className="text-lg font-medium text-colsubsidio-blue">
                Conversa con Protección Inteligente 360°
              </p>
              <p className="max-w-sm text-sm text-muted-foreground">
                Pregúntame sobre seguros de vida, hogar, vehículo,
                viajes, mascotas y más. Te ayudo a encontrar la protección que necesitás.
              </p>
            </div>
          ) : (
            <>
              <AnimatePresence initial={false}>
                {messages.map((msg, i) => (
                  <MessageBubble key={msg.id} message={msg} index={i} onButtonClick={handleButtonClick} />
                ))}
              </AnimatePresence>

              {/* Typing indicator */}
              {isLoading && <TypingIndicator />}

              {/* Error banner */}
              <AnimatePresence>
                {mutation.isError && (
                  <motion.div
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 8 }}
                    className="mx-4 mt-3 flex items-center gap-3 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm"
                  >
                    <AlertCircle className="size-4 shrink-0 text-destructive" />
                    <span className="flex-1 text-destructive-foreground">
                      No se pudo enviar el mensaje. Intenta de nuevo.
                    </span>
                    <button
                      onClick={handleRetry}
                      className="rounded-md bg-destructive px-3 py-1 text-xs font-medium text-destructive-foreground hover:bg-destructive/80 transition-colors"
                    >
                      Reintentar
                    </button>
                    <button
                      onClick={handleDismissError}
                      className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                    >
                      X
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>
            </>
          )}
        </div>
      </div>

      {/* Input bar */}
      <div className="flex items-center gap-2 border-x border-b rounded-b-xl bg-card p-4">
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Escribe tu mensaje..."
          disabled={isLoading}
          className="flex-1 rounded-lg border bg-background px-4 py-2.5 text-sm outline-none transition-colors placeholder:text-muted-foreground/50 focus:border-colsubsidio-blue/50 focus:ring-1 focus:ring-colsubsidio-blue/20 disabled:opacity-50"
        />
        <button
          onClick={handleSend}
          disabled={isLoading || !inputValue.trim()}
          className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-colsubsidio-blue text-white transition-all hover:bg-colsubsidio-blue/90 disabled:opacity-40 disabled:cursor-not-allowed"
          aria-label="Enviar mensaje"
        >
          {isLoading ? (
            <Loader2 className="size-5 animate-spin" />
          ) : (
            <Send className="size-5" />
          )}
        </button>
      </div>
    </div>
  );
}

import React, { useEffect, useMemo, useState } from "react";
import { Sparkles, FileText } from "lucide-react";

import NetworkStatus from "../components/security/NetworkStatus";
import ManagerPanel from "../components/admin/ManagerPanel";
import ArtifactLibrary from "../components/admin/ArtifactLibrary";
import ObservabilityPanel from "../components/admin/ObservabilityPanel";
import EncryptionStatusPanel from "../components/admin/EncryptionStatusPanel";
import NetworkEvidencePanel from "../components/security/NetworkEvidencePanel";
import AppLayout from "../components/layout/AppLayout";
import Header from "../components/layout/Header";
import EmptyState from "../components/common/EmptyState";
import SuggestionCards from "../components/chat/SuggestionCards";
import ChatInput from "../components/chat/ChatInput";
import MessageList from "../components/chat/MessageList";
import { useAuth } from "../context/AuthContext";
import { streamChat, health, conversationList, conversationMessages } from "../services/api";
import { conversationId, topicFrom, groupDate } from "../utils/conversation";
import { readJSON, writeJSON } from "../utils/storage";

const STORE = "sovereign_conversations";

const mapServerConversation = (c = {}) => ({
  id: c?.id,
  title: c?.title || "New conversation",
  createdAt: Date.parse(c?.created_at) || Date.now(),
  updatedAt: Date.parse(c?.updated_at) || Date.now(),
  messages: [],
  messageCount: c?.message_count || 0,
});

export default function Dashboard() {
  const { user, logout } = useAuth();
  const [convs, setConvs] = useState(() => readJSON(STORE, []));
  const [activeId, setActiveId] = useState(null);
  const [input, setInput] = useState("");
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [steps, setSteps] = useState([]);
  const [online, setOnline] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => writeJSON(STORE, convs), [convs]);

  useEffect(() => {
    if (!user) return;
    conversationList(user)
      .then((d) => {
        const server = Array.isArray(d?.conversations)
          ? d.conversations.map(mapServerConversation).filter((c) => c?.id)
          : [];
        setConvs(server.length ? server : readJSON(STORE, []));
      })
      .catch(() => {});
  }, [user?.employee_id, user?.employeeId, user?.role]);

  useEffect(() => {
    health()
      .then(() => setOnline(true))
      .catch(() => setOnline(false));
  }, []);

  const active = convs.find((c) => c?.id === activeId);

  const grouped = useMemo(() => {
    const map = {};
    convs
      .filter(Boolean)
      .slice()
      .sort((a, b) => (b?.updatedAt || 0) - (a?.updatedAt || 0))
      .forEach((c) => {
        const key = groupDate(c?.updatedAt || Date.now());
        if (!map[key]) map[key] = [];
        map[key].push(c);
      });
    return Object.values(map).flat();
  }, [convs]);

  const newChat = () => {
    setActiveId(null);
    setInput("");
    setFile(null);
    setSteps([]);
    setError("");
  };

  const open = async (id) => {
    setActiveId(id);
    setSteps([]);
    setError("");
    if (!id || id.startsWith("__")) return;

    try {
      const d = await conversationMessages(id, user);
      const msgs = Array.isArray(d?.messages)
        ? d.messages.map((m) => ({
            id: String(m?.id ?? crypto.randomUUID()),
            role: m?.role || "assistant",
            content: m?.content || "",
            fileName: m?.metadata?.file_name || null,
            taskType: m?.metadata?.task_type,
            model: m?.metadata?.model,
            createdAt: Date.parse(m?.created_at) || Date.now(),
          }))
        : [];

      setConvs((cs) => cs.map((c) =>
        c?.id === id
          ? { ...c, messages: msgs, updatedAt: Date.now(), messageCount: msgs.length }
          : c
      ));
    } catch (e) {
      setError(e?.message || "Unable to load conversation history.");
    }
  };

  const send = async () => {
    if (loading || (!input.trim() && !file)) return;

    const text = input.trim();
    const id = activeId || conversationId();
    const existing = convs.find((c) => c?.id === id);
    const now = Date.now();
    const conv = existing || {
      id,
      title: topicFrom(text || file?.name || "New conversation"),
      createdAt: now,
      updatedAt: now,
      messages: [],
    };

    const userMsg = {
      id: crypto.randomUUID(),
      role: "user",
      content: text || `Please analyze ${file?.name || "the attached file"}`,
      fileName: file?.name || null,
      createdAt: now,
    };

    setConvs((cs) => {
      if (existing) {
        return cs.map((c) => c?.id === id
          ? {
              ...c,
              updatedAt: now,
              messages: [...(Array.isArray(c?.messages) ? c.messages : []), userMsg],
            }
          : c
        );
      }
      return [{ ...conv, messages: [userMsg] }, ...cs];
    });

    setActiveId(id);
    setInput("");
    setLoading(true);
    setError("");
    setSteps([
      { key: "stage-INGESTION", status: "running", label: "INGESTION · Request and attachment" },
      { key: "stage-ROUTING", status: "pending", label: "ROUTING · Local model selection" },
      { key: "stage-COMPILATION", status: "pending", label: "COMPILATION · Execution plan" },
      { key: "stage-SANDBOX", status: "pending", label: "SANDBOX · Isolated execution" },
      { key: "stage-SYNTHESIS", status: "pending", label: "SYNTHESIS · Final response" },
      { key: "task", status: "running", label: "Sending request to FastAPI backend" },
    ]);

    try {
      await streamChat({
        message: text,
        conversationId: id,
        conversationHistory: (Array.isArray(existing?.messages) ? existing.messages : [])
          .slice(-8)
          .filter(Boolean)
          .map((m) => ({
            role: m?.role,
            content: m?.content,
            fileName: m?.fileName,
            taskType: m?.taskType,
            model: m?.model,
          })),
        file,
        user,
        onEvent: (ev, data = {}) => {
          if (ev === "stage") {
            const stage = data?.stage;
            if (!stage) return;
            setSteps((s) => s.filter(Boolean).map((x) =>
              x?.key === `stage-${stage}`
                ? {
                    ...x,
                    status: data?.status || x?.status || "running",
                    label: `${stage} · ${data?.label || "Workflow stage"}`,
                  }
                : x
            ));
          } else if (ev === "task") {
            setSteps((s) => {
              const nextSteps = s.filter(Boolean).filter((x) => x?.key?.startsWith("stage-"));
              nextSteps.push({
                key: "analysis",
                status: "completed",
                label: `Task identified: ${data?.task_analysis?.task_type || "Unknown task"}`,
              });

              if (data?.conversation_context?.is_follow_up) {
                nextSteps.push({
                  key: "context",
                  status: "completed",
                  label: `Follow-up detected · using ${data?.conversation_context?.message_count || 0} recent messages`,
                });
              }

              const routes = Array.isArray(data?.routes) ? data.routes : [];
              routes.filter(Boolean).forEach((r, i) => {
                const operation = r?.operation || "operation";
                nextSteps.push({
                  key: `route-${i}`,
                  status: "running",
                  label: `Routing ${String(operation).replace(/_/g, " ")}`,
                  model: r?.model_name || null,
                  ollama_model: r?.ollama_model || null,
                });
              });
              return nextSteps.filter(Boolean);
            });
          } else if (ev === "step") {
            const operation = data?.operation || "operation";
            const step = data?.step || "step";
            const stepKey = `${operation}-${step}`;
            setSteps((s) => [
              ...s.filter(Boolean).filter((x) => x?.key !== stepKey),
              {
                key: stepKey,
                status: data?.status || "running",
                label: data?.label || "Processing step",
                model: data?.model || null,
                ollama_model: data?.ollama_model || null,
              },
            ]);
          } else if (ev === "progress") {
            setSteps((s) => s.filter(Boolean).map((x) =>
              x?.status === "running"
                ? { ...x, label: data?.label || x?.label || "Processing" }
                : x
            ));
          } else if (ev === "error") {
            setError(data?.message || "Backend processing failed.");
          } else if (ev === "complete") {
            const r = data?.agent_result || {};
            const results = Array.isArray(r?.results) ? r.results.filter(Boolean) : [];
            const final = r?.final_response || r?.final_context || results.at(-1)?.response || "No response returned.";

            const files = results
              .filter((x) => x?.download_url)
              .map((x) => ({
                filename: x?.file?.filename || "generated.docx",
                download_url: x.download_url,
                title: x?.file?.title || x?.file?.filename || "Generated document",
              }))
              .concat(
                (Array.isArray(r?.generated_files) ? r.generated_files : [])
                  .filter((g) => g?.download_url && !results.some((x) => x?.download_url === g.download_url))
                  .map((g) => ({
                    filename: g?.filename || "generated-file",
                    download_url: g.download_url,
                    title: g?.title || g?.filename || "Generated file",
                  }))
              );

            const coding = results.find((x) => x?.operation === "coding");
            const modelResult = results.find((x) => x?.model);
            const draftResult = results.find(
              (x) => x?.operation === "draft_generation" && x?.requires_human_review && x?.human_review
            );

            const ai = {
              id: crypto.randomUUID(),
              role: "assistant",
              user,
              content: final,
              taskType: data?.task_analysis?.task_type || null,
              workflowState: data?.workbench_state || r?.workbench_state || null,
              model: coding?.model || modelResult?.model || null,
              files,
              approval: draftResult
                ? { review: draftResult.human_review, draft: draftResult.draft }
                : null,
              createdAt: Date.now(),
            };

            setConvs((cs) => cs.map((c) => c?.id === id
              ? {
                  ...c,
                  updatedAt: Date.now(),
                  messages: [...(Array.isArray(c?.messages) ? c.messages : []), ai],
                  messageCount: (Array.isArray(c?.messages) ? c.messages.length : 0) + 1,
                }
              : c
            ));

            setSteps((s) => s.filter(Boolean).map((x) =>
              x?.status === "running" ? { ...x, status: "completed" } : x
            ));
          }
        },
      });
      setFile(null);
    } catch (e) {
      if (e?.name !== "AbortError") setError(e?.message || "Unable to reach backend.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AppLayout
      user={user}
      conversations={grouped}
      activeId={activeId}
      onNewChat={newChat}
      onOpen={open}
      onLogout={logout}
    >
      <Header conversation={active}/>

      {user?.role === "Manager" && (
        <div className="manager-toggle">
          <button onClick={() => setActiveId("__manager__")}>
            <FileText size={15}/> Manager Console
          </button>
        </div>
      )}

      <div className="chat-body">
        {activeId === "__manager__" ? (
          <ManagerPanel user={user}/>
        ) : activeId === "__observability__" ? (
          <ObservabilityPanel user={user}/>
        ) : activeId === "__encryption__" ? (
          <EncryptionStatusPanel user={user}/>
        ) : activeId === "__network__" ? (
          <NetworkEvidencePanel user={user}/>
        ) : activeId === "__artifacts__" ? (
          <ArtifactLibrary user={user}/>
        ) : !Array.isArray(active?.messages) || active.messages.length === 0 ? (
          <EmptyState>
            <p>{online ? "Your local AI workspace is ready." : "Backend offline — start FastAPI on port 8000."}</p>
            <SuggestionCards onSelect={setInput}/>
          </EmptyState>
        ) : (
          <MessageList
            messages={Array.isArray(active?.messages) ? active.messages : []}
            loading={loading}
            steps={Array.isArray(steps) ? steps.filter(Boolean) : []}
          />
        )}

        {error && <div className="error banner">{error}</div>}
      </div>

      <ChatInput
        value={input}
        onChange={setInput}
        onSend={send}
        file={file}
        setFile={setFile}
        disabled={loading}
      />

      <div className="workspace-footer">
        <NetworkStatus/>
        <span><Sparkles size={13}/> {online ? "Air-gapped · local backend connected" : "Waiting for backend"}</span>
        <span>{user?.username || "User"} · {user?.role || "User"}</span>
      </div>
    </AppLayout>
  );
}

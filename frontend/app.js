// 期末复习助手 前端逻辑（vanilla）
const API = (window.API_BASE || "") + "/api";
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const el = (h) => { const d = document.createElement("div"); d.innerHTML = h.trim(); return d.firstChild; };
const esc = (s) => (s ?? "").toString().replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

async function api(path, opts = {}) {
  const r = await fetch(API + path, opts);
  if (!r.ok) throw new Error((await r.text()).slice(0, 200) || r.status);
  return r.json();
}
function busy(btn, on) {
  if (on) { btn.dataset.txt = btn.innerHTML; btn.innerHTML = '<span class="spin"></span>'; btn.disabled = true; }
  else { btn.innerHTML = btn.dataset.txt; btn.disabled = false; }
}
function masteryColor(m) { return m < 0.4 ? "var(--bad)" : m < 0.7 ? "var(--warn)" : "var(--ok)"; }

// ---- tabs ----
$$("nav button").forEach(b => b.onclick = () => {
  $$("nav button").forEach(x => x.classList.toggle("on", x === b));
  ["up", "an", "weak", "exam", "tutor"].forEach(t =>
    $("#t-" + t).classList.toggle("hide", t !== b.dataset.tab));
});

// ---- status ----
async function refreshStatus() {
  try {
    const s = await api("/status");
    $("#dry").classList.toggle("hide", !s.dry_run);
    $("#stat").textContent = `素材 ${s.materials} · 题目 ${s.questions} · 薄弱点 ${s.weak_points} · 卷子 ${s.exams}`;
  } catch (e) { $("#stat").textContent = "后端未连接：" + e.message; }
}

// ---- 上传 ----
// 前端压缩：手机照片动辄几 MB，压到长边 1600px 再传，避免 nginx 413、降带宽与成本。
async function compressImage(file, maxEdge = 1600, quality = 0.82) {
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise((res, rej) => {
      const i = new Image(); i.onload = () => res(i); i.onerror = rej; i.src = url;
    });
    let w = img.width, h = img.height;
    if (Math.max(w, h) > maxEdge) { const s = maxEdge / Math.max(w, h); w = Math.round(w * s); h = Math.round(h * s); }
    const c = document.createElement("canvas"); c.width = w; c.height = h;
    c.getContext("2d").drawImage(img, 0, 0, w, h);
    return await new Promise(r => c.toBlob(r, "image/jpeg", quality));
  } catch (e) { return null; } finally { URL.revokeObjectURL(url); }
}

$("#btnUp").onclick = async () => {
  const files = [...$("#files").files];
  if (!files.length) return alert("请先选择图片");
  busy($("#btnUp"), true);
  $("#upList").innerHTML = "";
  const prog = el('<div class="card" id="upProg"></div>'); $("#upList").appendChild(prog);
  let done = 0, ok = 0;
  // 逐张上传：每个请求只含一张压缩图，既不超限也不会因 61 张同步分析而超时
  for (const f of files) {
    prog.textContent = `上传分析中… ${done}/${files.length}（成功 ${ok}）`;
    try {
      const blob = (await compressImage(f)) || f;
      const fd = new FormData();
      fd.append("files", blob, (f.name || "img") + ".jpg");
      fd.append("auto_extract", "true");
      const r = await api("/upload", { method: "POST", body: fd });
      (r.uploaded || []).forEach(it => renderUploadOne(it, prog));
      ok++;
    } catch (e) { renderUploadOne({ error: e.message, filename: f.name }, prog); }
    done++;
  }
  prog.textContent = `完成：成功 ${ok}/${files.length}`;
  refreshStatus();
  busy($("#btnUp"), false);
};
function renderUploadOne(it, prog) {
  const ex = it.extracted;
  let qs = "";
  if (ex) qs = (ex.questions || []).map(q => `
    <div class="q ${q.is_correct ? "" : "wrong"}">
      <div><b>${esc(q.number)}.</b> ${esc(q.stem)}</div>
      <div class="muted">作答：<span class="${q.is_correct ? "right" : "wrongtxt"}">${esc(q.child_answer)}</span>
        ${q.is_correct ? '✔' : '✘ 正确：' + esc(q.correct_answer)}</div>
      ${(q.knowledge_points || []).map(k => `<span class="tag">${esc(k)}</span>`).join("")}
      ${q.error_type ? `<div class="muted">错因：${esc(q.error_type)}</div>` : ""}
    </div>`).join("");
  const card = el(`<div class="card">
    <b>${it.material_id ? "素材 #" + it.material_id : esc(it.filename || "")}</b>
    ${ex ? `· ${esc(ex.subject)} · ${esc(ex.source)}` : ""}
    ${it.error ? `<span class="wrongtxt">分析失败：${esc(it.error)}</span>` : ""}${qs}</div>`);
  prog.after(card);
}

// ---- 全局分析 / 知识树 ----
$("#btnGlobal").onclick = async () => {
  busy($("#btnGlobal"), true);
  try {
    const g = await api("/analyze/global", { method: "POST" });
    $("#globalSummary").textContent = g.summary || "";
    await loadKnowledge();
  } catch (e) { alert(e.message); } finally { busy($("#btnGlobal"), false); }
};
async function loadKnowledge() {
  const k = await api("/knowledge");
  const box = $("#kpList"); box.innerHTML = "";
  k.knowledge_points.forEach(kp => {
    const m = kp.mastery ?? 0.5;
    box.appendChild(el(`<div class="q">
      <label class="ck" style="background:none;padding:0">
        <input type="checkbox" class="kpck" value="${esc(kp.name)}">
        <b>${esc(kp.name)}</b> <span class="muted">${esc(kp.subject || "")} · 出现${kp.frequency}次 · ${esc(kp.difficulty || "")}${kp.beyond_syllabus ? " · 超纲" : ""}</span>
      </label>
      <div class="bar"><i style="width:${Math.round(m * 100)}%;background:${masteryColor(m)}"></i></div>
      <div class="muted">掌握度 ${Math.round(m * 100)}%</div>
    </div>`));
  });
  buildExamSources(k.knowledge_points);
}

// ---- 薄弱点 ----
$("#btnWeak").onclick = async () => {
  busy($("#btnWeak"), true);
  try { renderWeak(await api("/analyze/weak", { method: "POST" })); refreshStatus(); }
  catch (e) { alert(e.message); } finally { busy($("#btnWeak"), false); }
};
function renderWeak(r) {
  const box = $("#weakList"); box.innerHTML = "";
  (r.weak_points || []).forEach(w => {
    const card = el(`<div class="card">
      <div class="row" style="justify-content:space-between">
        <b>${esc(w.knowledge_point)}</b>
        <span class="muted">掌握 ${Math.round((w.mastery ?? 0) * 100)}%</span></div>
      <div class="muted">${esc(w.why || "")}</div>
      ${(w.typical_errors || []).map(e => `<span class="tag">${esc(e)}</span>`).join("")}
      <div class="row" style="margin-top:8px">
        <button class="btn sec sm bExp">一键讲解+练习</button>
        <button class="btn sm bTut">去 AI 老师辅导</button></div>
      <div class="expOut"></div></div>`);
    card.querySelector(".bExp").onclick = async (e) => {
      busy(e.target, true);
      try {
        const x = await api("/weak/explain", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ knowledge_point: w.knowledge_point, errors: w.typical_errors })
        });
        card.querySelector(".expOut").innerHTML = `
          <div class="q"><b>讲解</b><div>${esc(x.explanation)}</div>
          <div class="muted">例题：${esc(x.worked_example)}</div>
          <b>练习</b>${(x.practice || []).map((p, i) => `
            <div class="q">${i + 1}. ${esc(p.stem)}<div class="muted">答案：${esc(p.answer)}｜${esc(p.explanation)}</div></div>`).join("")}</div>`;
      } catch (err) { alert(err.message); } finally { busy(e.target, false); }
    };
    card.querySelector(".bTut").onclick = () => {
      $$("nav button").find(b => b.dataset.tab === "tutor").click();
      $("#tutorKp").value = w.knowledge_point; $("#btnTutorStart").click();
    };
    box.appendChild(card);
  });
}

// ---- 模拟卷 ----
function buildExamSources(kps) {
  const box = $("#exSources"); box.innerHTML = "";
  box.appendChild(el(`<label class="ck"><input type="checkbox" id="srcAuto" checked>全局自动抽选</label>`));
  box.appendChild(el(`<label class="ck"><input type="checkbox" id="srcFocus" checked>圈选重点(知识树勾选)</label>`));
  box.appendChild(el(`<label class="ck"><input type="checkbox" id="srcWeak" checked>孩子薄弱点</label>`));
}
$("#btnExam").onclick = async () => {
  const focus = $$(".kpck:checked").map(c => c.value);
  let weak = [];
  try { weak = (await api("/weak")).map(w => w.knowledge_point); } catch (e) {}
  const body = {
    subject: $("#exSubject").value, num: +$("#exNum").value, total: +$("#exTotal").value,
    auto_points: ($("#srcAuto") && $("#srcAuto").checked) ? null : [],
    focus_points: ($("#srcFocus") && $("#srcFocus").checked) ? focus : [],
    weak_points: ($("#srcWeak") && $("#srcWeak").checked) ? weak : [],
  };
  busy($("#btnExam"), true);
  try { renderExam(await api("/exam/generate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })); refreshStatus(); }
  catch (e) { alert(e.message); } finally { busy($("#btnExam"), false); }
};
function renderExam(p) {
  let n = 0;
  const secs = (p.sections || []).map(s => `<h3>${esc(s.name)}</h3>` +
    (s.questions || []).map(q => `<div class="q"><b>${esc(q.number || ++n)}.</b> (${q.score}分) ${esc(q.stem)}
      <span class="answer hide muted">答案：${esc(q.answer)}</span>
      ${(q.knowledge_points || []).map(k => `<span class="tag noprint">${esc(k)}</span>`).join("")}
      ${q.source ? `<span class="tag noprint">来源:${esc(q.source)}</span>` : ""}</div>`).join("")).join("");
  $("#examOut").innerHTML = `<div class="card">
    <div class="row noprint" style="justify-content:space-between">
      <b>${esc(p.title)}</b>
      <div><button class="btn sec sm" id="bAns">显示/隐藏答案</button>
      <button class="btn sm" onclick="window.print()">打印 PDF</button></div></div>
    <div class="muted">总分 ${p.total_score} · 建议 ${p.duration_min || "—"} 分钟</div>
    ${secs}</div>`;
  $("#bAns").onclick = () => $$("#examOut .answer").forEach(a => a.classList.toggle("hide"));
}

// ---- AI 老师 ----
let tutorSid = null, tutorImgFile = null;
$("#btnTutorStart").onclick = async () => {
  const kp = $("#tutorKp").value.trim(); if (!kp) return alert("请输入知识点");
  busy($("#btnTutorStart"), true);
  try {
    const r = await api("/tutor/start", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ knowledge_point: kp }) });
    tutorSid = r.session_id; $("#tutorBox").classList.remove("hide"); $("#chat").innerHTML = "";
    pushMsg("t", r.reply); if (r.ask_back) pushMsg("t", r.ask_back);
  } catch (e) { alert(e.message); } finally { busy($("#btnTutorStart"), false); }
};
function pushMsg(who, text) {
  const c = $("#chat"); c.appendChild(el(`<div class="msg ${who}">${esc(text)}</div>`)); c.scrollTop = c.scrollHeight;
}
$("#btnTutorImg").onclick = () => $("#tutorImg").click();
$("#tutorImg").onchange = e => { tutorImgFile = e.target.files[0]; if (tutorImgFile) pushMsg("c", "📷 已附手写照片"); };
$("#btnVoice").onclick = () => alert("语音对话（ASR/TTS）为三期功能，先用打字/拍照提问～");
$("#btnTutorSay").onclick = async () => {
  if (!tutorSid) return; const t = $("#tutorIn").value.trim();
  if (!t && !tutorImgFile) return;
  if (t) pushMsg("c", t);
  const fd = new FormData(); fd.append("text", t || "（见手写照片）");
  if (tutorImgFile) fd.append("image", tutorImgFile);
  $("#tutorIn").value = ""; tutorImgFile = null; busy($("#btnTutorSay"), true);
  try {
    const r = await api(`/tutor/${tutorSid}/say`, { method: "POST", body: fd });
    pushMsg("t", r.reply); if (r.ask_back) pushMsg("t", r.ask_back);
    if (r.mastered) pushMsg("t", "🎉 看起来你已经懂啦！可以点下面出题考察一下。");
  } catch (e) { alert(e.message); } finally { busy($("#btnTutorSay"), false); }
};
$("#btnTutorCheck").onclick = async () => {
  if (!tutorSid) return; const ans = $("#tutorAns").value.trim(); if (!ans) return;
  busy($("#btnTutorCheck"), true);
  try {
    const r = await api(`/tutor/${tutorSid}/check`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ knowledge_point: $("#tutorKp").value.trim(), subject: "数学", answers: ans })
    });
    pushMsg("t", (r.mastered ? "✅ 判定：已掌握！" : "还需巩固：") + (r.comment || ""));
  } catch (e) { alert(e.message); } finally { busy($("#btnTutorCheck"), false); }
};

// init
refreshStatus();
if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});

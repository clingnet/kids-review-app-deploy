/**
 * api.js — 全页面共用 API 封装
 * 所有页面 <script src="api.js"> 先于页面脚本引入
 */

const API = '/api';

/**
 * 通用 fetch 辅助（JSON 请求/响应）
 * @param {string} path  — /api 后面的路径，如 '/dashboard'
 * @param {object} opts  — fetch options（method, body 等）
 * @returns {Promise<any>} — 解析后的 JSON 数据
 */
async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    ...opts,
  });
  if (!res.ok) {
    const errText = await res.text().catch(() => '');
    throw new Error(`API ${path} 失败 (${res.status}): ${errText}`);
  }
  return res.json();
}

/**
 * multipart/form-data 上传辅助
 * @param {string} path   — /api 后面的路径
 * @param {FormData} formData
 * @returns {Promise<any>}
 */
async function apiForm(path, formData) {
  const res = await fetch(API + path, {
    method: 'POST',
    body: formData,
    // 不设 Content-Type，让浏览器自动设置 multipart boundary
  });
  if (!res.ok) {
    const errText = await res.text().catch(() => '');
    throw new Error(`API ${path} 失败 (${res.status}): ${errText}`);
  }
  return res.json();
}

/**
 * 友好错误提示（显示到指定容器，或 console）
 * @param {string|Error} err
 * @param {HTMLElement|null} container — 若传入则把错误渲染进去
 */
function showApiError(err, container = null) {
  const msg = err instanceof Error ? err.message : String(err);
  console.error('[API Error]', msg);
  if (container) {
    container.innerHTML = `<div style="color:#ff6090;font-size:.82rem;padding:12px;border:1px solid rgba(255,45,120,.3);border-radius:8px;background:rgba(255,45,120,.06);">⚠ ${escHtmlGlobal(msg)}</div>`;
  }
}

/** HTML 转义（全局可用） */
function escHtmlGlobal(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * 轮询 /analysis/status，version 增加时调用 onUpdate 回调
 * @param {function} onUpdate — 传入最新 status 对象
 * @param {number} intervalMs — 轮询间隔，默认 5000ms
 * @returns {function} — 调用返回值可停止轮询
 */
function pollAnalysisStatus(onUpdate, intervalMs = 5000) {
  let lastVersion = null;
  let tid = null;

  async function check() {
    try {
      const status = await api('/analysis/status');
      if (lastVersion === null) {
        lastVersion = status.version;
      } else if (status.version !== lastVersion) {
        lastVersion = status.version;
        onUpdate(status);
      }
    } catch (e) {
      // 轮询失败静默处理
    }
  }

  check();
  tid = setInterval(check, intervalMs);

  return () => clearInterval(tid);
}

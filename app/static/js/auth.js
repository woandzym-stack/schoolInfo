/**
 * 全站共享认证模块（登录/注册弹窗 + 修改密码弹窗 + 登录态管理）。
 *
 * 用法（页面需先引入 vue / element-plus，再引入本文件）：
 *   1. 模板内放 <auth-modal></auth-modal>（修改密码页额外放 <change-password-modal></change-password-modal>）
 *   2. app.component('auth-modal', SchoolAuth.AuthModal) 注册后再 mount
 *   3. SchoolAuth.init() 探测登录态；SchoolAuth.requireLogin(fn) 未登录先弹登录框、成功后自动续上 fn
 *
 * 登录态约定：JWT 在 HttpOnly Cookie 里，前端不接触 token；所有请求同源 fetch 自动携带。
 */
window.SchoolAuth = (function () {
  // 弹窗样式随模块自带：el-dialog append-to-body 后 teleport 到 <body>，
  // 脱离页面 #app 作用域，页面里的样式覆盖不到它，必须在这里注入。
  // 色值优先取页面 :root 变量，兜底值与站点主题（墨蓝/印章红/衬线刊头）一致。
  function _injectStyle() {
    if (document.getElementById('school-auth-style')) return;
    const el = document.createElement('style');
    el.id = 'school-auth-style';
    el.textContent = [
      '.auth-dialog { border-radius: 6px; }',
      '.auth-dialog .el-dialog__header { margin-right: 0; padding-bottom: 6px; }',
      '.auth-dialog .el-dialog__title {',
      '  font-family: "Noto Serif TC", serif; font-weight: 700; letter-spacing: 1px;',
      '}',
      '.auth-brand { display: flex; align-items: center; gap: 10px; }',
      '.auth-brand-seal {',
      '  width: 34px; height: 34px; flex: none;',
      '  background: var(--seal, #B3392E); color: #FFF7F0;',
      '  font-family: "Noto Serif TC", serif; font-weight: 700; font-size: 19px;',
      '  display: inline-flex; align-items: center; justify-content: center;',
      '  border-radius: 5px;',
      '  box-shadow: 0 2px 5px rgba(179, 57, 46, .3), inset 0 0 0 2px rgba(255, 247, 240, .35);',
      '  transform: rotate(-3deg); user-select: none;',
      '}',
      '.auth-brand-name {',
      '  font-family: "Noto Serif TC", serif; font-size: 17px; font-weight: 700;',
      '  color: var(--ink, #1E2A44); letter-spacing: 1px;',
      '}',
      '.auth-dialog .el-tabs__nav-wrap::after { background: var(--hairline, #D9DFE8); height: 1px; }',
      '.auth-dialog .el-tabs__item {',
      '  font-family: "Noto Serif TC", serif; font-size: 15px; font-weight: 600;',
      '  color: var(--slate, #5A6B85);',
      '}',
      '.auth-dialog .el-tabs__item:hover, .auth-dialog .el-tabs__item.is-active { color: var(--ink, #1E2A44); }',
      '.auth-dialog .el-tabs__active-bar { background: var(--seal, #B3392E); height: 3px; }',
      '.auth-dialog .el-input__wrapper { border-radius: 4px; }',
      '.auth-dialog .el-button--primary {',
      '  --el-button-bg-color: var(--ink, #1E2A44);',
      '  --el-button-border-color: var(--ink, #1E2A44);',
      '  --el-button-hover-bg-color: var(--el-color-primary-light-3, #4A5878);',
      '  --el-button-hover-border-color: var(--el-color-primary-light-3, #4A5878);',
      '  --el-button-active-bg-color: var(--el-color-primary-dark-2, #16203A);',
      '  --el-button-active-border-color: var(--el-color-primary-dark-2, #16203A);',
      '  font-weight: 700; border-radius: 4px; letter-spacing: 2px;',
      '}',
    ].join('\n');
    document.head.appendChild(el);
  }
  _injectStyle();

  const state = Vue.reactive({
    user: null,            // {id, username, email} | null
    loaded: false,         // /auth/me 探测是否已完成
    dialogVisible: false,
    activeTab: 'login',
    submitting: false,
    loginForm: { username: '', password: '' },
    registerForm: { username: '', password: '', email: '' },
    pwdVisible: false,     // 修改密码弹窗
    pwdSubmitting: false,
    pwdForm: { old_password: '', new_password: '', confirm: '' },
    _afterLogin: null,     // 登录成功后要续上的动作（如订阅）
  });

  // 统一 API 封装：信封 {errCode, errMsg, data}，非成功码抛出带 HTTP status 的 Error。
  // 401 分两种：匿名探测（/auth/me，state.user 本就为 null）属正常路径，只抛错；
  // 持有登录态时收到 401 说明会话已失效（Cookie 过期/其他标签页退出），
  // 必须清态并弹登录框，否则页面会一直显示已登录、受保护操作反复失败。
  async function api(path, opts) {
    const options = opts || {};
    const resp = await fetch(path, {
      method: options.method || 'GET',
      headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
    const body = await resp.json().catch(function () { return null; });
    if (!resp.ok || !body || (body.errCode !== 200 && body.errCode !== 0)) {
      const err = new Error((body && body.errMsg) || ('HTTP ' + resp.status));
      err.status = resp.status;
      if (resp.status === 401 && state.user) {
        state.user = null;
        ElementPlus.ElMessage({ message: '登录已过期，请重新登录', type: 'warning', grouping: true });
        openDialog('login');
      }
      throw err;
    }
    return body.data;
  }

  async function init() {
    try {
      state.user = await api('/api/v1/auth/me');
    } catch (e) {
      state.user = null;   // 401 即未登录，属正常路径
    } finally {
      state.loaded = true;
    }
    return state.user;
  }

  function openDialog(tab) {
    state.activeTab = tab || 'login';
    state.dialogVisible = true;
  }

  /** 未登录先弹登录框，登录成功后自动执行 action */
  function requireLogin(action) {
    if (state.user) {
      action();
    } else {
      state._afterLogin = action;
      openDialog('login');
    }
  }

  function _onLoginSuccess(user) {
    state.user = user;
    state.dialogVisible = false;
    state.loginForm = { username: '', password: '' };
    state.registerForm = { username: '', password: '', email: '' };
    const action = state._afterLogin;
    state._afterLogin = null;
    if (action) action();
  }

  async function submitLogin() {
    const f = state.loginForm;
    if (!f.username.trim() || !f.password) {
      ElementPlus.ElMessage.warning('请输入用户名和密码');
      return;
    }
    state.submitting = true;
    try {
      const user = await api('/api/v1/auth/login', { method: 'POST', body: f });
      ElementPlus.ElMessage.success('登录成功');
      _onLoginSuccess(user);
    } catch (e) {
      ElementPlus.ElMessage.error(e.message);
    } finally {
      state.submitting = false;
    }
  }

  async function submitRegister() {
    const f = state.registerForm;
    if (!f.username.trim() || !f.password || !f.email.trim()) {
      ElementPlus.ElMessage.warning('请填写完整注册信息');
      return;
    }
    if (f.password.length < 8 || !/[A-Za-z]/.test(f.password) || !/\d/.test(f.password)) {
      ElementPlus.ElMessage.warning('密码需至少 8 位，且同时包含字母和数字');
      return;
    }
    state.submitting = true;
    try {
      const user = await api('/api/v1/auth/register', { method: 'POST', body: f });
      ElementPlus.ElMessage.success('注册成功，已自动登录');
      _onLoginSuccess(user);
    } catch (e) {
      ElementPlus.ElMessage.error(e.message);
    } finally {
      state.submitting = false;
    }
  }

  // 退出靠服务端响应头删 HttpOnly Cookie：只有请求成功才算真正退出。
  // 失败（断网/5xx）时 Cookie 仍有效，必须保留前端登录态并允许重试，
  // 否则刷新页面会"复活"登录。
  async function logout() {
    try {
      await api('/api/v1/auth/logout', { method: 'POST' });
    } catch (e) {
      ElementPlus.ElMessage.error('退出失败，请检查网络后重试');
      return false;
    }
    state.user = null;
    ElementPlus.ElMessage.success('已退出登录');
    return true;
  }

  function openChangePassword() {
    state.pwdForm = { old_password: '', new_password: '', confirm: '' };
    state.pwdVisible = true;
  }

  async function submitChangePassword() {
    const f = state.pwdForm;
    if (!f.old_password || !f.new_password) {
      ElementPlus.ElMessage.warning('请填写原密码和新密码');
      return;
    }
    if (f.new_password.length < 8 || !/[A-Za-z]/.test(f.new_password) || !/\d/.test(f.new_password)) {
      ElementPlus.ElMessage.warning('新密码需至少 8 位，且同时包含字母和数字');
      return;
    }
    if (f.new_password !== f.confirm) {
      ElementPlus.ElMessage.warning('两次输入的新密码不一致');
      return;
    }
    state.pwdSubmitting = true;
    try {
      await api('/api/v1/auth/password', {
        method: 'PUT',
        body: { old_password: f.old_password, new_password: f.new_password },
      });
      state.pwdVisible = false;
      ElementPlus.ElMessage.success('密码修改成功');
    } catch (e) {
      ElementPlus.ElMessage.error(e.message);
    } finally {
      state.pwdSubmitting = false;
    }
  }

  // ---------- 弹窗组件（模板依赖页面已全局注册 ElementPlus） ----------
  const AuthModal = {
    template: [
      '<el-dialog v-model="state.dialogVisible" class="auth-dialog" width="400px" :show-close="true" align-center append-to-body>',
      '  <template #header>',
      '    <div class="auth-brand"><span class="auth-brand-seal">插</span><span class="auth-brand-name">香港插班 · 学校名录</span></div>',
      '  </template>',
      '  <el-tabs v-model="state.activeTab" stretch>',
      '    <el-tab-pane label="登录" name="login">',
      '      <el-form @submit.prevent>',
      '        <el-form-item><el-input v-model="state.loginForm.username" placeholder="用户名" size="large" /></el-form-item>',
      '        <el-form-item><el-input v-model="state.loginForm.password" type="password" placeholder="密码" size="large" show-password @keyup.enter="submitLogin" /></el-form-item>',
      '        <el-button type="primary" size="large" style="width:100%" :loading="state.submitting" @click="submitLogin">登录</el-button>',
      '      </el-form>',
      '    </el-tab-pane>',
      '    <el-tab-pane label="注册" name="register">',
      '      <el-form @submit.prevent>',
      '        <el-form-item><el-input v-model="state.registerForm.username" placeholder="用户名（3-32 位）" size="large" /></el-form-item>',
      '        <el-form-item><el-input v-model="state.registerForm.password" type="password" placeholder="密码（至少 8 位，含字母和数字）" size="large" show-password /></el-form-item>',
      '        <el-form-item><el-input v-model="state.registerForm.email" placeholder="邮箱（用于接收插班信息推送）" size="large" @keyup.enter="submitRegister" /></el-form-item>',
      '        <el-button type="primary" size="large" style="width:100%" :loading="state.submitting" @click="submitRegister">注册并登录</el-button>',
      '      </el-form>',
      '    </el-tab-pane>',
      '  </el-tabs>',
      '</el-dialog>',
    ].join('\n'),
    data: function () { return { state: state }; },
    methods: { submitLogin: submitLogin, submitRegister: submitRegister },
  };

  const ChangePasswordModal = {
    template: [
      '<el-dialog v-model="state.pwdVisible" class="auth-dialog" title="修改密码" width="400px" align-center append-to-body>',
      '  <el-form @submit.prevent>',
      '    <el-form-item><el-input v-model="state.pwdForm.old_password" type="password" placeholder="原密码" size="large" show-password /></el-form-item>',
      '    <el-form-item><el-input v-model="state.pwdForm.new_password" type="password" placeholder="新密码（至少 8 位，含字母和数字）" size="large" show-password /></el-form-item>',
      '    <el-form-item><el-input v-model="state.pwdForm.confirm" type="password" placeholder="再次输入新密码" size="large" show-password @keyup.enter="submit" /></el-form-item>',
      '    <el-button type="primary" size="large" style="width:100%" :loading="state.pwdSubmitting" @click="submit">确认修改</el-button>',
      '  </el-form>',
      '</el-dialog>',
    ].join('\n'),
    data: function () { return { state: state }; },
    methods: { submit: submitChangePassword },
  };

  return {
    state: state,
    api: api,
    init: init,
    openDialog: openDialog,
    requireLogin: requireLogin,
    logout: logout,
    openChangePassword: openChangePassword,
    AuthModal: AuthModal,
    ChangePasswordModal: ChangePasswordModal,
  };
})();

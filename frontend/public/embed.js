/**
 * 报告AI解读 - 悬浮球嵌入脚本
 *
 * 在任意网页（如卫宁EMR）中嵌入此脚本，即可显示悬浮球。
 * 点击悬浮球打开侧边面板，面板通过 iframe 加载解读系统。
 *
 * 使用方法：
 * 在EMR页面的HTML中加入一行：
 * <script src="http://你的服务器IP:3000/embed.js"><\/script>
 *
 * 或让卫宁驻场在EMR页面模板中注入以下代码：
 * <script>
 *   (function() {
 *     var s = document.createElement('script');
 *     s.src = 'http://你的服务器IP:3000/embed.js';
 *     document.body.appendChild(s);
 *   })();
 * <\/script>
 */
(function () {
  'use strict';

  // 配置（可根据实际部署修改）
  var CONFIG = {
    serverUrl: window.REPORT_AI_URL || (location.protocol + '//' + location.hostname + ':3000'),
    ballSize: 56,
    ballColor: '#1677ff',
    panelWidth: 420,
    zIndex: 99999,
  };

  // 防止重复注入
  if (document.getElementById('report-ai-float-ball')) return;

  // 创建样式
  var style = document.createElement('style');
  style.textContent = [
    '#report-ai-float-ball {',
    '  position: fixed;',
    '  top: 200px;',
    '  right: 20px;',
    '  width: ' + CONFIG.ballSize + 'px;',
    '  height: ' + CONFIG.ballSize + 'px;',
    '  border-radius: 50%;',
    '  background: linear-gradient(135deg, #1677ff, #0958d9);',
    '  color: #fff;',
    '  display: flex;',
    '  flex-direction: column;',
    '  align-items: center;',
    '  justify-content: center;',
    '  cursor: pointer;',
    '  box-shadow: 0 4px 16px rgba(22,119,255,0.4);',
    '  z-index: ' + CONFIG.zIndex + ';',
    '  transition: all 0.3s;',
    '  user-select: none;',
    '  font-family: -apple-system, "Microsoft YaHei", sans-serif;',
    '}',
    '#report-ai-float-ball:hover {',
    '  transform: scale(1.08);',
    '  box-shadow: 0 6px 24px rgba(22,119,255,0.5);',
    '}',
    '#report-ai-float-ball .ball-icon {',
    '  font-size: 20px;',
    '  font-weight: bold;',
    '}',
    '#report-ai-float-ball .ball-text {',
    '  font-size: 10px;',
    '  font-weight: 700;',
    '  margin-top: -2px;',
    '}',
    '#report-ai-panel {',
    '  position: fixed;',
    '  top: 0;',
    '  right: 0;',
    '  width: ' + CONFIG.panelWidth + 'px;',
    '  height: 100vh;',
    '  background: #fff;',
    '  box-shadow: -4px 0 24px rgba(0,0,0,0.12);',
    '  z-index: ' + (CONFIG.zIndex + 1) + ';',
    '  transition: transform 0.3s ease;',
    '  transform: translateX(100%);',
    '}',
    '#report-ai-panel.open {',
    '  transform: translateX(0);',
    '}',
    '#report-ai-panel iframe {',
    '  width: 100%;',
    '  height: 100%;',
    '  border: none;',
    '}',
    '#report-ai-panel-close {',
    '  position: absolute;',
    '  top: 10px;',
    '  right: 10px;',
    '  width: 28px;',
    '  height: 28px;',
    '  border-radius: 50%;',
    '  background: #ff4d4f;',
    '  color: #fff;',
    '  border: none;',
    '  cursor: pointer;',
    '  font-size: 16px;',
    '  display: flex;',
    '  align-items: center;',
    '  justify-content: center;',
    '  z-index: ' + (CONFIG.zIndex + 2) + ';',
    '}',
  ].join('\n');
  document.head.appendChild(style);

  // 创建悬浮球
  var ball = document.createElement('div');
  ball.id = 'report-ai-float-ball';
  ball.innerHTML = '<span class="ball-icon">🔬</span><span class="ball-text">AI</span>';
  document.body.appendChild(ball);

  // 创建侧边面板
  var panel = document.createElement('div');
  panel.id = 'report-ai-panel';

  var closeBtn = document.createElement('button');
  closeBtn.id = 'report-ai-panel-close';
  closeBtn.innerHTML = '✕';
  panel.appendChild(closeBtn);

  var iframe = document.createElement('iframe');
  iframe.src = CONFIG.serverUrl + '/embed-inner';
  panel.appendChild(iframe);
  document.body.appendChild(panel);

  // 状态
  var isOpen = false;

  // 点击悬浮球
  ball.addEventListener('click', function () {
    isOpen = !isOpen;
    if (isOpen) {
      panel.classList.add('open');
      // 尝试传递当前页面中的患者信息给 iframe
      try {
        var patientId = extractPatientId();
        if (patientId) {
          iframe.src = CONFIG.serverUrl + '/embed-inner?pid=' + patientId;
        }
      } catch (e) { /* ignore */ }
    } else {
      panel.classList.remove('open');
    }
  });

  // 关闭按钮
  closeBtn.addEventListener('click', function (e) {
    e.stopPropagation();
    isOpen = false;
    panel.classList.remove('open');
  });

  // 拖拽悬浮球
  var dragStartY, dragStartTop;
  ball.addEventListener('mousedown', function (e) {
    dragStartY = e.clientY;
    dragStartTop = ball.offsetTop;
    var moved = false;

    function onMove(ev) {
      var diff = ev.clientY - dragStartY;
      if (Math.abs(diff) > 3) moved = true;
      ball.style.top = Math.max(60, Math.min(window.innerHeight - 80, dragStartTop + diff)) + 'px';
    }
    function onUp() {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      if (moved) {
        // 阻止这次click
        ball.addEventListener('click', function prevent(ev) {
          ev.stopImmediatePropagation();
          ball.removeEventListener('click', prevent, true);
        }, true);
      }
    }
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });

  /**
   * 尝试从当前EMR页面提取患者住院号
   * 此函数需要根据卫宁EMR实际页面结构进行适配
   */
  function extractPatientId() {
    // 方式1：从URL参数提取
    var params = new URLSearchParams(window.location.search);
    var pid = params.get('patient_id') || params.get('patientId') || params.get('pid');
    if (pid) return pid;

    // 方式2：从页面元素提取（需根据实际EMR页面调整选择器）
    var selectors = [
      '[data-patient-id]',
      '#patientId',
      '#patient_id',
      '.patient-id',
      'input[name="patientId"]',
    ];
    for (var i = 0; i < selectors.length; i++) {
      var el = document.querySelector(selectors[i]);
      if (el) {
        return el.getAttribute('data-patient-id') || el.value || el.textContent.trim();
      }
    }

    return null;
  }

})();

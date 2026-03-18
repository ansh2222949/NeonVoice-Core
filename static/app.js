/* NeonAI: Frontend logic (UI, chat, settings). */

const toggle = document.querySelector(".liquid-toggle");
const config = {
  complete: 100,
  active: false,
  deviation: 2,
  alpha: 16,
  bounce: true,
  hue: 200,
  delta: true,
  bubble: true,
  mapped: false,
};

const ICON_MARKUP = {
  volumeOff: `
    <svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M11 5 6 9H3v6h3l5 4V5Z"></path>
      <path d="m16 9 5 6"></path>
      <path d="m21 9-5 6"></path>
    </svg>
  `,
  volumeOn: `
    <svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M11 5 6 9H3v6h3l5 4V5Z"></path>
      <path d="M16.5 8.5a5 5 0 0 1 0 7"></path>
      <path d="M19.5 5a9 9 0 0 1 0 14"></path>
    </svg>
  `,
  mic: `
    <svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <rect x="9" y="3" width="6" height="12" rx="3"></rect>
      <path d="M5 11a7 7 0 0 0 14 0"></path>
      <path d="M12 18v3"></path>
      <path d="M8 21h8"></path>
    </svg>
  `,
  keyboard: `
    <svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <rect x="3" y="6" width="18" height="12" rx="2"></rect>
      <path d="M7 10h.01"></path>
      <path d="M10 10h.01"></path>
      <path d="M13 10h.01"></path>
      <path d="M16 10h.01"></path>
      <path d="M8 14h8"></path>
    </svg>
  `,
  wave: `
    <svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M4 14V10"></path>
      <path d="M8 17V7"></path>
      <path d="M12 20V4"></path>
      <path d="M16 17V7"></path>
      <path d="M20 14V10"></path>
    </svg>
  `,
};

function getIconMarkup(name) {
  return ICON_MARKUP[name] || "";
}

function setSoundToggleState(isMuted) {
  const soundToggle = document.getElementById("soundToggle");
  const soundIcon = document.getElementById("soundIcon");
  if (!soundToggle || !soundIcon) return;

  soundToggle.dataset.muted = String(isMuted);
  soundToggle.setAttribute(
    "aria-label",
    isMuted ? "Unmute wallpaper video" : "Mute wallpaper video",
  );
  soundIcon.innerHTML = getIconMarkup(isMuted ? "volumeOff" : "volumeOn");
}

function syncSoundToggle() {
  const bgVid = document.getElementById("bg-video");
  const soundToggle = document.getElementById("soundToggle");
  if (!bgVid || !soundToggle) return;

  const hasVideoSource = Boolean(bgVid.getAttribute("src") || bgVid.currentSrc);
  soundToggle.disabled = !hasVideoSource;
  soundToggle.classList.toggle("is-idle", !hasVideoSource);
  setSoundToggleState(bgVid.muted);
}

function applyBackgroundModeState(mode = readStorage("bgMode") || "none") {
  if (!document.body) return;

  const normalizedMode = mode || "none";
  const hasCustomWallpaper = normalizedMode === "custom" || normalizedMode === "video";

  document.body.dataset.bgMode = normalizedMode;
  document.body.classList.toggle("has-custom-wallpaper", hasCustomWallpaper);
  document.body.classList.toggle("has-video-wallpaper", normalizedMode === "video");
  syncBackgroundVideoPlayback();
  updateWallpaperStatusLine();
}

function updateWallpaperStatusLine() {
  const el = document.getElementById("bgStatusLine");
  if (!el) return;

  const mode = readStorage("bgMode") || "none";
  const url = readStorage("bgCustomUrl") || "";

  if (mode === "video") {
    el.innerText = "Current: Video wallpaper";
    return;
  }
  if (mode === "custom") {
    el.innerText = "Current: Image wallpaper";
    return;
  }
  if (mode === "none") {
    el.innerText = "Current: Default";
    return;
  }
  // preset name (stored as preset key)
  if (url && (mode === "custom" || mode === "video")) {
    el.innerText = "Current: Custom";
    return;
  }
  el.innerText = `Current: Preset (${mode})`;
}

function setVoiceToggleContent(button, isVoiceMode) {
  if (!button) return;

  button.innerHTML = `
    <span class="voice-toggle-content" style="display: flex; align-items: center; justify-content: center; width: 100%; height: 100%;">
      <span class="voice-toggle-icon" aria-hidden="true" style="display: flex;">${getIconMarkup(isVoiceMode ? "keyboard" : "mic")}</span>
    </span>
  `;
  button.setAttribute(
    "aria-label",
    isVoiceMode ? "Switch to text input" : "Switch to voice input",
  );
}

gsap.set(toggle, { "--complete": config.complete });
toggle.setAttribute("aria-pressed", "true");

const updateFilters = () => {
  gsap.set("#goo feGaussianBlur", { attr: { stdDeviation: config.deviation } });
  gsap.set("#goo feColorMatrix", {
    attr: { values: `1 0 0 0 0 0 1 0 0 0 0 0 1 0 0 0 0 0 ${config.alpha} -10` },
  });
  toggle.style.setProperty("--complete", config.complete);
  toggle.style.setProperty("--hue", config.hue);
};

const switchThemeMode = (isDark) => {
  if (isDark) {
    document.body.classList.remove("light-mode");
  } else {
    document.body.classList.add("light-mode");
  }
};

const toggleState = async () => {
  toggle.dataset.pressed = true;
  if (config.bubble) toggle.dataset.active = true;

  await Promise.allSettled(
    !config.bounce
      ? toggle.getAnimations({ subtree: true }).map((a) => a.finished)
      : [],
  );

  const pressed = toggle.getAttribute("aria-pressed") === "true";

  gsap
    .timeline({
      onComplete: () => {
        gsap.delayedCall(0.05, () => {
          toggle.dataset.active = false;
          toggle.dataset.pressed = false;
          const newState = !toggle.matches("[aria-pressed=true]");
          toggle.setAttribute("aria-pressed", newState);
          switchThemeMode(newState);
        });
      },
    })
    .to(toggle, {
      "--complete": pressed ? 0 : 100,
      duration: 0.12,
      delay: config.bounce && config.bubble ? 0.18 : 0,
    });
};

if (toggle) {
  toggle.addEventListener("click", toggleState);
  updateFilters();

  if (toggle._dragProxy) {
    Draggable.get(toggle._dragProxy)?.kill();
  }
  const proxy = document.createElement("div");
  toggle._dragProxy = proxy;
  Draggable.create(proxy, {
    trigger: toggle,
    type: "x",
    onDragStart: function () {
      this.startX = this.x;
      toggle.dataset.active = true;
    },
    onDrag: function () {
      const pressed = toggle.matches("[aria-pressed=true]");
      let dragPercent = ((this.x - this.startX) / 60) * 100;
      let complete = pressed ? 100 + dragPercent : dragPercent;
      complete = Math.max(0, Math.min(100, complete));
      config.complete = complete;
      updateFilters();
    },
    onDragEnd: function () {
      toggle.dataset.active = false;
      const finalState = config.complete > 50;
      gsap.to(toggle, {
        "--complete": finalState ? 100 : 0,
        duration: 0.2,
        onComplete: () => {
          toggle.setAttribute("aria-pressed", finalState);
          switchThemeMode(finalState);
        },
      });
    },
  });
}

function getUserAvatar() {
  return (
    readStorage("userProfilePic") ||
    "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"
  );
}

const allThemes = [
  "theme-emerald",
  "theme-cyber",
  "theme-blue",
  "theme-purple",
  "theme-gold",
  "theme-red",
  "theme-lime",
  "theme-ice",
  "theme-obsidian",
  "theme-rgb",
  "theme-sunset",
  "theme-aurora",
  "theme-ocean",
  "theme-tokyo",
  "theme-rosegold",
];
const MOVIE_CACHE_TTL_MS = 5 * 60 * 1000;
const TRENDING_RENDER_BATCH_SIZE = 6;
const MAX_GSAP_CARD_ANIMATIONS = 12;
const SCRAMBLE_SELECTOR = "h1, h2, .chat-name-tag, .card-text";
const storageCache = new Map();
const textScrambleFrames = new WeakMap();
let cachedTrendingMovies = [];
let cachedTrendingAt = 0;
let cachedTrendingKey = "";
let trendingMoviesRequest = null;
let voiceUiInitialized = false;
let currentMovies = [];
let autoScrollInterval = null;
let trendingRenderToken = 0;
let isMovieCarouselInView = true;
let movieCarouselObserver = null;
const AUTO_SCROLL_SPEED = 0.5;

function _getNsKey(key) {
  const uid = window.USER_ID || 'anon';
  return `${key}_${uid}`;
}

function readStorage(key) {
  const nsKey = _getNsKey(key);
  if (storageCache.has(nsKey)) {
    return storageCache.get(nsKey);
  }
  const value = localStorage.getItem(nsKey);
  storageCache.set(nsKey, value);
  return value;
}

function writeStorage(key, value) {
  const nsKey = _getNsKey(key);
  const normalizedValue = String(value);
  storageCache.set(nsKey, normalizedValue);
  localStorage.setItem(nsKey, normalizedValue);
}

function removeStorage(key) {
  const nsKey = _getNsKey(key);
  storageCache.delete(nsKey);
  localStorage.removeItem(nsKey);
}

window.addEventListener("storage", (event) => {
  if (!event.key) {
    storageCache.clear();
    return;
  }
  storageCache.set(event.key, event.newValue);
});

function prefersReducedMotion() {
  return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function scheduleIdleTask(task, timeout = 800) {
  if ("requestIdleCallback" in window) {
    window.requestIdleCallback(task, { timeout });
    return;
  }
  window.setTimeout(task, 1);
}

function scheduleChatScroll(container, behavior = "smooth") {
  if (!container || container._scrollScheduled) return;
  container._scrollScheduled = true;
  requestAnimationFrame(() => {
    container._scrollScheduled = false;
    container.scrollTo({
      top: container.scrollHeight,
      behavior,
    });
  });
}

function nextAnimationFrame() {
  return new Promise((resolve) => {
    requestAnimationFrame(() => resolve());
  });
}

function playInlineVideo(video) {
  if (!video) return;
  const playPromise = video.play();
  if (playPromise && typeof playPromise.catch === "function") {
    playPromise.catch(() => { });
  }
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function getFloatingButtonInset(button, edge) {
  const pxValue = Number.parseFloat(window.getComputedStyle(button)[edge]);
  return Number.isFinite(pxValue) ? pxValue : 12;
}

function clampFloatingButtonPosition(button, draggableInstance) {
  if (!button) return;

  const currentX = Number(gsap.getProperty(button, "x")) || 0;
  const currentY = Number(gsap.getProperty(button, "y")) || 0;
  const rect = button.getBoundingClientRect();
  const insetRight = getFloatingButtonInset(button, "right");
  const insetBottom = getFloatingButtonInset(button, "bottom");
  const insetTop = 12;
  const insetLeft = 12;

  const minX = currentX + (insetLeft - rect.left);
  const maxX = currentX + ((window.innerWidth - insetRight) - rect.right);
  const minY = currentY + (insetTop - rect.top);
  const maxY = currentY + ((window.innerHeight - insetBottom) - rect.bottom);

  const nextX = clamp(currentX, minX, maxX);
  const nextY = clamp(currentY, minY, maxY);

  gsap.set(button, { x: nextX, y: nextY });
  if (draggableInstance?.applyBounds) {
    draggableInstance.applyBounds(document.body);
  }
  writeStorage("voiceBtnPos", JSON.stringify({ x: nextX, y: nextY }));
}

function bindLoopCap(video, maxSeconds = 15) {
  if (!video) return;
  clearLoopCap(video);

  const clearTimer = () => {
    if (video._loopCapTimer) {
      window.clearTimeout(video._loopCapTimer);
      video._loopCapTimer = null;
    }
  };

  const scheduleCap = () => {
    clearTimer();

    const hasSource = Boolean(video.getAttribute("src") || video.currentSrc);
    if (!hasSource || video.paused) return;

    if (
      Number.isFinite(video.duration) &&
      video.duration > 0 &&
      video.duration <= maxSeconds + 0.25
    ) {
      return;
    }

    const remainingMs = Math.max(0, (maxSeconds - video.currentTime) * 1000);
    video._loopCapTimer = window.setTimeout(() => {
      clearTimer();
      if (video.paused) return;
      video.currentTime = 0;
      playInlineVideo(video);
      scheduleCap();
    }, remainingMs);
  };

  video._loopCapHandler = scheduleCap;
  video._loopCapClear = clearTimer;

  video.addEventListener("play", scheduleCap);
  video.addEventListener("loadedmetadata", scheduleCap);
  video.addEventListener("seeking", scheduleCap);
  video.addEventListener("ratechange", scheduleCap);
  video.addEventListener("pause", clearTimer);
  video.addEventListener("emptied", clearTimer);

  scheduleCap();
}

function clearLoopCap(video) {
  if (!video || !video._loopCapHandler) return;
  video.removeEventListener("play", video._loopCapHandler);
  video.removeEventListener("loadedmetadata", video._loopCapHandler);
  video.removeEventListener("seeking", video._loopCapHandler);
  video.removeEventListener("ratechange", video._loopCapHandler);
  video.removeEventListener("pause", video._loopCapClear);
  video.removeEventListener("emptied", video._loopCapClear);
  video._loopCapClear();
  video._loopCapClear = null;
  video._loopCapHandler = null;
}

function syncBackgroundVideoPlayback() {
  const bgVid = document.getElementById("bg-video");
  if (!bgVid) return;

  const hasVideoSource = Boolean(bgVid.getAttribute("src") || bgVid.currentSrc);
  const inVideoMode = document.body?.dataset.bgMode === "video";
  const shouldPlay =
    hasVideoSource &&
    inVideoMode &&
    !document.hidden &&
    !prefersReducedMotion();

  if (!hasVideoSource || !inVideoMode) {
    bgVid.classList.remove("playing");
  } else {
    bgVid.classList.add("playing");
  }

  if (!shouldPlay) {
    bgVid.pause();
    clearLoopCap(bgVid);
    syncSoundToggle();
    return;
  }

  bindLoopCap(bgVid, 15);
  playInlineVideo(bgVid);
  syncSoundToggle();
}

function syncVoiceVideoPlayback(resetToStart = false) {
  const voiceVideo = document.getElementById("voice-video-bg");
  if (!voiceVideo) return;

  const hasVideoSource = Boolean(voiceVideo.getAttribute("src") || voiceVideo.currentSrc);
  const shouldPlay =
    hasVideoSource &&
    inputMode === "voice" &&
    !document.hidden &&
    !prefersReducedMotion();

  if (!shouldPlay) {
    voiceVideo.pause();
    voiceVideo.classList.remove("playing");
    clearLoopCap(voiceVideo);
    return;
  }

  if (resetToStart) {
    voiceVideo.currentTime = 0;
  }

  voiceVideo.classList.add("playing");
  bindLoopCap(voiceVideo, 15);
  playInlineVideo(voiceVideo);
}

function shouldAutoScrollCarousel(wrapper = document.querySelector(".cards-wrapper")) {
  const carousel = document.getElementById("movie-carousel");
  return Boolean(
    wrapper &&
    carousel &&
    currentChatMode === "movie" &&
    carousel.style.display !== "none" &&
    !document.hidden &&
    !prefersReducedMotion() &&
    !document.body.classList.contains("voice-mode-active") &&
    isMovieCarouselInView,
  );
}

function observeMovieCarouselVisibility() {
  if (movieCarouselObserver || !("IntersectionObserver" in window)) return;

  const carousel = document.getElementById("movie-carousel");
  if (!carousel) return;

  movieCarouselObserver = new IntersectionObserver(
    (entries) => {
      isMovieCarouselInView = entries[0]?.isIntersecting ?? true;
      if (isMovieCarouselInView) {
        startAutoScroll();
      } else {
        stopAutoScroll();
      }
    },
    {
      threshold: 0.2,
    },
  );

  movieCarouselObserver.observe(carousel);
}

function bindMovieCarouselInteractions(wrapper) {
  if (!wrapper || wrapper.dataset.carouselBound === "true") return;
  wrapper.dataset.carouselBound = "true";

  wrapper.addEventListener("click", (event) => {
    const card = event.target.closest(".movie-card-placeholder");
    if (!card || !wrapper.contains(card)) return;

    const index = Number(card.dataset.movieIndex);
    if (!Number.isFinite(index)) return;
    openMovieDetails(index, event);
  });

  wrapper.addEventListener("mouseenter", stopAutoScroll);
  wrapper.addEventListener("mouseleave", startAutoScroll);
  wrapper.addEventListener(
    "touchstart",
    () => {
      if (wrapper._autoScrollResumeTimeout) {
        window.clearTimeout(wrapper._autoScrollResumeTimeout);
        wrapper._autoScrollResumeTimeout = null;
      }
      stopAutoScroll();
    },
    { passive: true },
  );
  wrapper.addEventListener(
    "touchend",
    () => {
      if (wrapper._autoScrollResumeTimeout) {
        window.clearTimeout(wrapper._autoScrollResumeTimeout);
      }
      wrapper._autoScrollResumeTimeout = window.setTimeout(() => {
        wrapper._autoScrollResumeTimeout = null;
        startAutoScroll();
      }, 2000);
    },
    { passive: true },
  );
}

function triggerTextScramble(el) {
  if (!el || textScrambleFrames.has(el)) return;

  const hasChildElements = Array.from(el.childNodes).some(
    (node) => node.nodeType === Node.ELEMENT_NODE,
  );
  if (hasChildElements) return;

  const originalText = el.textContent || "";
  if (!originalText.trim()) return;

  const letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  const originalChars = originalText.split("");
  const duration = Math.max(240, originalChars.length * 42);
  let startTime = null;

  const step = (timestamp) => {
    if (!el.isConnected) {
      textScrambleFrames.delete(el);
      return;
    }

    if (startTime === null) {
      startTime = timestamp;
    }

    const progress = Math.min((timestamp - startTime) / duration, 1);
    const revealCount = Math.floor(progress * originalChars.length);
    const nextText = originalChars
      .map((letter, index) => {
        if (index < revealCount) return letter;
        if (letter === " " || letter === "\n") return letter;
        return letters[Math.floor(Math.random() * letters.length)];
      })
      .join("");

    if (el.textContent !== nextText) {
      el.textContent = nextText;
    }

    if (progress >= 1) {
      el.textContent = originalText;
      textScrambleFrames.delete(el);
      return;
    }

    const frameId = requestAnimationFrame(step);
    textScrambleFrames.set(el, frameId);
  };

  const frameId = requestAnimationFrame(step);
  textScrambleFrames.set(el, frameId);
}

function bindTextScrambleHover() {
  if (document.body.dataset.scrambleBound) return;
  document.body.dataset.scrambleBound = "true";

  document.addEventListener("pointerover", (event) => {
    const target = event.target.closest(SCRAMBLE_SELECTOR);
    if (!target) return;
    if (event.relatedTarget && target.contains(event.relatedTarget)) return;
    triggerTextScramble(target);
  });
}

// ✅ 3D ICON EFFECT — Applied to any .ai-n-logo element
function apply3DIconEffect(logoEl) {
  if (!logoEl || logoEl.dataset.tilt3d) return;
  logoEl.dataset.tilt3d = "true";

  logoEl.style.transition = "transform 0.12s ease, box-shadow 0.12s ease, text-shadow 0.12s ease";
  logoEl.style.cursor = "default";
  logoEl.style.display = "inline-flex";
  logoEl.style.alignItems = "center";
  logoEl.style.justifyContent = "center";
  logoEl.style.willChange = "transform";

  const state = {
    dx: 0,
    dy: 0,
    frame: null,
    rect: null,
  };

  const updateRect = () => {
    state.rect = logoEl.getBoundingClientRect();
  };

  const renderTilt = () => {
    state.frame = null;
    const rotX = -state.dy * 25;
    const rotY = state.dx * 25;
    const glow = `${state.dx * 4}px ${state.dy * 4}px 18px rgba(0,255,255,0.55)`;

    logoEl.style.transform = `perspective(300px) rotateX(${rotX}deg) rotateY(${rotY}deg) scale(1.18)`;
    logoEl.style.boxShadow = glow;
    logoEl.style.textShadow = `${state.dx * 3}px ${state.dy * 3}px 10px rgba(0,255,255,0.8)`;
  };

  logoEl.addEventListener("pointerenter", updateRect, { passive: true });
  logoEl.addEventListener(
    "pointermove",
    (event) => {
      if (prefersReducedMotion()) return;

      if (!state.rect) {
        updateRect();
      }
      if (!state.rect || !state.rect.width || !state.rect.height) return;

      const cx = state.rect.left + state.rect.width / 2;
      const cy = state.rect.top + state.rect.height / 2;
      state.dx = (event.clientX - cx) / (state.rect.width / 2);
      state.dy = (event.clientY - cy) / (state.rect.height / 2);

      if (state.frame !== null) return;
      state.frame = requestAnimationFrame(renderTilt);
    },
    { passive: true },
  );

  logoEl.addEventListener("pointerleave", () => {
    if (state.frame !== null) {
      cancelAnimationFrame(state.frame);
      state.frame = null;
    }
    state.rect = null;
    logoEl.style.transform = "perspective(300px) rotateX(0deg) rotateY(0deg) scale(1)";
    logoEl.style.boxShadow = "";
    logoEl.style.textShadow = "";
  });
}

// Apply 3D to static logo in header/navbar if present
function applyGlobal3DLogo() {
  document.querySelectorAll(".ai-n-logo").forEach(apply3DIconEffect);
}

function ensureVoiceModeInitialized() {
  if (voiceUiInitialized) return;
  voiceUiInitialized = true;
  initVoiceMode();
}

document.addEventListener("DOMContentLoaded", () => {
  // Fetch server-persisted profile pic, voice video, bg video
  fetch('/auth/me').then(r => r.json()).then(data => {
    if (!data.logged_in) return;
    // Restore profile pic from server if available
    if (data.profile_pic) {
      const url = data.profile_pic + '?v=' + Date.now();
      const displayPic = document.getElementById('displayProfilePic');
      if (displayPic) displayPic.src = url;
      writeStorage("userProfilePic", url);
      document.querySelectorAll('.chat-user-pic').forEach(img => img.src = url);
      const voiceDp = document.getElementById('voice-dp-img');
      if (voiceDp) voiceDp.src = url;
    }
    // Restore voice video from server if available
    if (data.voice_video) {
      const vid = document.getElementById('voice-video-bg');
      if (vid && !vid.getAttribute('src')) {
        vid.src = data.voice_video + '?v=' + Date.now();
        vid.load();
        const nameDisplay = document.getElementById('voiceVideoName');
        if (nameDisplay) nameDisplay.innerText = 'Saved video';
      } else {
        window.__pendingVoiceVideoUrl = data.voice_video;
      }
    }
    // Restore bg video from server if available
    if (data.bg_video) {
      const bgMode = readStorage("bgMode");
      if (!bgMode || bgMode === 'video') {
        const bgVid = document.getElementById('bg-video');
        if (bgVid) {
          bgVid.src = data.bg_video + '?v=' + Date.now();
          bgVid.load();
          bgVid.currentTime = 0;
          document.documentElement.style.setProperty('--bg-image', 'none');
          writeStorage("bgMode", "video");
          writeStorage("bgCustomUrl", data.bg_video);
          applyBackgroundModeState('video');
        }
      }
    }
    if (data.bg_image) {
      const bgMode = readStorage("bgMode");
      if (!bgMode || bgMode === 'custom') {
        const bgUrl = data.bg_image + '?v=' + Date.now();
        document.documentElement.style.setProperty("--bg-image", `url('${bgUrl}')`);
        writeStorage("bgMode", "custom");
        writeStorage("bgCustomUrl", data.bg_image);
        applyBackgroundModeState('custom');
      }
    }
    syncSoundToggle();
    // Restore LLM provider and key status from server
    restoreLLMSettings(data);
  }).catch(() => {
    syncSoundToggle();
  });

  const bgMode = readStorage("bgMode");
  if (bgMode === "custom") {
    const customUrl = readStorage("bgCustomUrl") || "/static/wallpapers/current_bg.jpg";
    const bgUrl = customUrl + (customUrl.includes('?') ? '&' : '?') + "v=" + new Date().getTime();
    document.documentElement.style.setProperty("--bg-image", `url('${bgUrl}')`);
  } else if (bgMode && bgMode !== "video" && bgMode !== "none") {
    document.documentElement.style.setProperty("--bg-image", "var(--" + bgMode + ")");
    const bgPresetSelect = document.getElementById("bgPresetSelect");
    if (bgPresetSelect) bgPresetSelect.value = bgMode;
  } else if (bgMode === "none") {
    document.documentElement.style.setProperty("--bg-image", "none");
  }

  applyBackgroundModeState(bgMode || "none");

  const savedTheme = readStorage("userTheme");
  if (savedTheme) {
    handleThemeChange(savedTheme, true);
    const themeSelect = document.getElementById("themeSelect");
    if (themeSelect) themeSelect.value = savedTheme;
  }
  const name = readStorage("userName");
  if (name) {
    const userNameField = document.getElementById("userName");
    const welcomeName = document.getElementById("welcomeName");
    if (userNameField) userNameField.value = name;
    if (welcomeName) welcomeName.innerText = name;
  }
  const email = readStorage("userEmail");
  const userEmailField = document.getElementById("userEmail");
  if (email && userEmailField) userEmailField.value = email;

  const savedPic = readStorage("userProfilePic");
  const displayPic = document.getElementById("displayProfilePic");
  if (savedPic && displayPic) displayPic.src = savedPic;

  handleModeChange(true);
  const modeSelect = document.getElementById("modeSelect");
  if (modeSelect && modeSelect.value === "movie") loadTrendingMovies();
  observeMovieCarouselVisibility();

  const neonLogo = document.getElementById("neon-logo");
  if (neonLogo) {
    neonLogo.style.flexShrink = "0";
    neonLogo.style.objectFit = "contain";
    neonLogo.style.aspectRatio = "1/1";
  }

  const inputField = document.getElementById("userInput");
  if (inputField) {
    const btn =
      inputField.nextElementSibling ||
      inputField.parentElement.querySelector("button");
    if (btn) {
      const icon = btn.querySelector("svg") || btn.querySelector("i") || btn;
      if (icon) icon.classList.add("send-icon-anim");
      btn.classList.add("send-btn-hover-effect");
    }
  }

  scheduleIdleTask(() => {
    applyGlobal3DLogo();
    bindTextScrambleHover();
    ensureVoiceModeInitialized();
  }, 500);
});

function toggleDrawer() {
  const drawer = document.getElementById("drawer");
  const overlay = document.getElementById("drawer-overlay");
  const isOpen = drawer.classList.toggle("open");
  overlay.classList.toggle("active");
  document.body.style.overflow = isOpen ? "hidden" : "";
}

function handleThemeChange(theme, skipSave = false) {
  const classesToRemove = [];
  document.body.classList.forEach(cls => {
    if (cls.startsWith('theme-')) classesToRemove.push(cls);
  });
  if (classesToRemove.length > 0) {
    document.body.classList.remove(...classesToRemove);
  }
  document.body.classList.add(theme);

  document.querySelectorAll('.theme-circle').forEach(circle => {
    circle.classList.remove('selected');
  });
  const activeCircle = document.querySelector(`.theme-circle[data-theme="${theme}"]`);
  if (activeCircle) activeCircle.classList.add('selected');

  if (!skipSave) writeStorage("userTheme", theme);
}

function changeProfilePic() {
  const fileInput = document.getElementById("profileUpload");
  if (fileInput.files && fileInput.files[0]) {
    const file = fileInput.files[0];
    const reader = new FileReader();
    reader.onload = function (e) {
      const imgData = e.target.result;
      const displayPic = document.getElementById("displayProfilePic");
      if (displayPic) displayPic.src = imgData;
      writeStorage("userProfilePic", imgData);
      document.querySelectorAll(".chat-user-pic").forEach((img) => {
        img.src = imgData;
      });
      // Update voice mode DP too
      const voiceDp = document.getElementById("voice-dp-img");
      if (voiceDp) voiceDp.src = imgData;
    };
    reader.readAsDataURL(file);

    // Save to server for persistence
    const formData = new FormData();
    formData.append("file", file);
    fetch("/upload-profile-pic", { method: "POST", body: formData })
      .then(r => r.json())
      .then(data => {
        if (data.status === "success") console.log("[Profile] DP saved to server");
      })
      .catch(() => { });
  }
}

function saveProfile() {
  const userNameField = document.getElementById("userName");
  const name = userNameField ? userNameField.value || "User" : "User";
  writeStorage("userName", name);

  const userEmailField = document.getElementById("userEmail");
  if (userEmailField) {
    writeStorage("userEmail", userEmailField.value);
  }

  const welcomeName = document.getElementById("welcomeName");
  if (welcomeName) welcomeName.innerText = name;

  document
    .querySelectorAll(".user-name-label")
    .forEach((tag) => (tag.innerText = name));
}

function setThinkingState(isThinking) {
  const logo = document.getElementById("neon-logo");
  const text = document.getElementById("neon-name");
  const chatContainer = document.getElementById("chat-container");
  const bubbleId = "thinking-bubble-loader";

  if (logo && text) {
    if (isThinking) {
      logo.classList.add("spin");
      text.classList.add("text-thinking-multi");

      if (chatContainer && !document.getElementById(bubbleId)) {
        const bubbleRow = document.createElement("div");
        bubbleRow.id = bubbleId;
        bubbleRow.className = "chat-row assistant";
        bubbleRow.innerHTML = `
          <div class="chat-avatar-container">
             <div class="ai-avatar-multiglow"></div><div class="ai-n-logo">N</div>
          </div>
          <div class="msg-column">
             <div class="chat-name-tag">Neon AI</div>
             <div class="msg" style="padding: 15px 20px;">
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
             </div>
          </div>`;
        chatContainer.appendChild(bubbleRow);
        // ✅ Apply 3D to newly created logo
        apply3DIconEffect(bubbleRow.querySelector(".ai-n-logo"));
        scheduleChatScroll(chatContainer);
      }
    } else {
      logo.classList.remove("spin");
      text.classList.remove("text-thinking-multi");
      text.style.color = "var(--primary-glow)";

      const bubble = document.getElementById(bubbleId);
      if (bubble) bubble.remove();
    }
  }
}

async function changeWallpaper() {
  const fileInput = document.getElementById("bgUpload");
  if (!fileInput.files[0]) return;
  const file = fileInput.files[0];
  const isVideo = file.type.startsWith('video/');
  const bgVideo = document.getElementById('bg-video');
  const bgDisplay = document.getElementById("bgNameDisplay");
  const progWrap = document.getElementById("bgUploadProgress");
  const progBar = document.getElementById("bgUploadProgressBar");
  const MAX_BG_VIDEO_MB = 50;
  const MAX_BG_IMAGE_MB = 10;

  const sizeMb = file.size / (1024 * 1024);
  if (isVideo && sizeMb > MAX_BG_VIDEO_MB) {
    addMsg(`That video is ${sizeMb.toFixed(1)}MB. Please pick a video under ${MAX_BG_VIDEO_MB}MB.`, "assistant");
    fileInput.value = "";
    return;
  }
  if (!isVideo && sizeMb > MAX_BG_IMAGE_MB) {
    addMsg(`That image is ${sizeMb.toFixed(1)}MB. Please pick an image under ${MAX_BG_IMAGE_MB}MB.`, "assistant");
    fileInput.value = "";
    return;
  }

  if (bgDisplay) {
    const labelType = isVideo ? "Video" : "Image";
    bgDisplay.innerText = `${labelType}: ${file.name} (${sizeMb.toFixed(1)}MB)`;
  }

  if (isVideo) {
    // Video wallpaper — play as fullscreen background with 15s loop
    const blobUrl = URL.createObjectURL(file);
    if (bgVideo) {
      bgVideo.src = blobUrl;
      bgVideo.load();
      bgVideo.currentTime = 0;
      // Clear image bg
      document.documentElement.style.setProperty('--bg-image', 'none');
      applyBackgroundModeState("video");
    }
  } else {
    // Image wallpaper — classic behavior
    const reader = new FileReader();
    reader.onload = function (e) {
      document.documentElement.style.setProperty(
        "--bg-image",
        `url(${e.target.result})`,
      );
      applyBackgroundModeState("custom");
    };
    reader.readAsDataURL(file);
    // Stop video bg if switching to image
    if (bgVideo) {
      bgVideo.pause();
      bgVideo.removeAttribute('src');
      bgVideo.load();
      bgVideo.classList.remove('playing');
      clearLoopCap(bgVideo);
    }
  }

  setThinkingState(true);
  const formData = new FormData();
  formData.append("file", file);
  try {
    if (progWrap && progBar) {
      progWrap.style.display = "block";
      progBar.style.width = "0%";
    }

    const data = await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/upload-bg", true);
      xhr.responseType = "json";
      xhr.upload.onprogress = (evt) => {
        if (!evt.lengthComputable) return;
        const pct = Math.max(0, Math.min(100, (evt.loaded / evt.total) * 100));
        if (progBar) progBar.style.width = pct.toFixed(0) + "%";
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) return resolve(xhr.response || {});
        // Backend may send JSON error message
        return resolve(xhr.response || { status: "error", message: `Upload failed (${xhr.status})` });
      };
      xhr.onerror = () => reject(new Error("Upload failed"));
      xhr.send(formData);
    });

    setThinkingState(false);
    if (progWrap) progWrap.style.display = "none";
    if (data.status === "success") {
      writeStorage("bgMode", isVideo ? "video" : "custom");
      writeStorage("bgCustomUrl", data.url);
      applyBackgroundModeState(isVideo ? "video" : "custom");
      if (bgDisplay) bgDisplay.innerText = isVideo ? "Video Saved" : "Image Saved";
      addMsg(isVideo ? "Video Wallpaper Activated." : "Wallpaper Secured.", "assistant");
    } else {
      addMsg(data.message || "Background upload failed.", "assistant");
    }
  } catch (e) {
    setThinkingState(false);
    if (progWrap) progWrap.style.display = "none";
    addMsg("Background upload failed. Please try again.", "assistant");
  }
}

function attachWallpaperDropAndRemove() {
  const dropZone = document.getElementById("bgDropZone");
  const fileInput = document.getElementById("bgUpload");
  const removeBtn = document.getElementById("bgRemoveBtn");
  const bgVideo = document.getElementById("bg-video");

  if (dropZone && fileInput) {
    const prevent = (e) => {
      e.preventDefault();
      e.stopPropagation();
    };

    ["dragenter", "dragover"].forEach((evt) => {
      dropZone.addEventListener(evt, (e) => {
        prevent(e);
        dropZone.classList.add("drop-active");
      });
    });
    ["dragleave", "drop"].forEach((evt) => {
      dropZone.addEventListener(evt, (e) => {
        prevent(e);
        dropZone.classList.remove("drop-active");
      });
    });

    dropZone.addEventListener("drop", (e) => {
      const dt = e.dataTransfer;
      if (!dt || !dt.files || !dt.files.length) return;
      fileInput.files = dt.files;
      changeWallpaper();
    });
  }

  if (removeBtn) {
    removeBtn.addEventListener("click", async () => {
      if (!confirm("Remove your custom wallpaper and revert to default/preset?")) return;
      setThinkingState(true);
      try {
        const res = await fetch("/clear-bg", { method: "POST" });
        const data = await res.json();
        setThinkingState(false);
        if (data.status === "success") {
          // Stop video if active
          if (bgVideo) {
            bgVideo.pause();
            bgVideo.removeAttribute("src");
            bgVideo.load();
            bgVideo.classList.remove("playing");
          }
          document.documentElement.style.setProperty("--bg-image", "none");
          writeStorage("bgMode", "none");
          writeStorage("bgCustomUrl", "");
          applyBackgroundModeState("none");
          const bgDisplay = document.getElementById("bgNameDisplay");
          if (bgDisplay) bgDisplay.innerText = "Upload Image / Video";
          addMsg("Custom wallpaper removed.", "assistant");
        } else {
          addMsg(data.message || "Failed to remove wallpaper.", "assistant");
        }
      } catch (e) {
        setThinkingState(false);
        addMsg("Failed to remove wallpaper.", "assistant");
      }
    });
  }
}

// Attach once on load
window.addEventListener("load", attachWallpaperDropAndRemove);

// Store chat history per mode using separate containers
let currentChatMode = "casual";

function getOrCreateModeContainer(modeValue) {
  const chatContainer = document.getElementById("chat-container");
  if (!chatContainer) return null;

  let wrapper = chatContainer.querySelector(`[data-mode-chat="${modeValue}"]`);
  if (!wrapper) {
    wrapper = document.createElement("div");
    wrapper.setAttribute("data-mode-chat", modeValue);
    wrapper.style.display = "none";
    wrapper.style.width = "100%";
    chatContainer.appendChild(wrapper);
  }
  return wrapper;
}

function handleModeChange(isInit = false) {
  const select = document.getElementById("modeSelect");
  if (!select) return;

  const modeValue = select.value;
  const modeText = select.options[select.selectedIndex].text;

  const modeHints = {
    casual: "General assistant",
    movie: "Movies & shows",
    exam: "Exam & syllabus",
    voice_assistant: "Voice commands & conversation",
  };
  const modeHint = document.getElementById("mode-hint");
  if (modeHint) modeHint.innerText = modeHints[modeValue] || "";

  const neonName = document.getElementById("neon-name");
  if (neonName) {
    if (neonName.innerText !== modeText) {
      neonName.classList.remove("text-switch-anim");
      void neonName.offsetWidth; // trigger reflow
      neonName.classList.add("text-switch-anim");
      neonName.innerText = modeText;
    } else {
      neonName.innerText = modeText;
    }
  }

  const examUpload = document.getElementById("examUpload");
  if (examUpload) {
    examUpload.style.display = modeValue === "exam" ? "block" : "none";
  }

  const carousel = document.getElementById("movie-carousel");

  stopAutoScroll();

  if (carousel) {
    if (modeValue === "movie") {
      carousel.style.display = "block";
      loadTrendingMovies();
    } else {
      carousel.style.display = "none";
    }
  }

  // Auto-switch to voice mode when voice_assistant is selected
  if (modeValue === "voice_assistant") {
    ensureVoiceModeInitialized();
    activateVoiceMode();
  } else {
    deactivateVoiceMode();
  }

  // --- PER-MODE CHAT ISOLATION ---
  const chatContainer = document.getElementById("chat-container");
  if (chatContainer) {
    // Hide ALL mode containers
    chatContainer.querySelectorAll("[data-mode-chat]").forEach(el => {
      el.style.display = "none";
    });

    // Show (or create) container for the selected mode
    const modeContainer = getOrCreateModeContainer(modeValue);
    if (modeContainer) {
      modeContainer.style.display = "block";

      // If this mode container is empty and not init, add welcome message
      if (!isInit && modeContainer.children.length === 0 && modeValue !== currentChatMode) {
        // Temporarily set this as the active mode so addMsg places messages here
        currentChatMode = modeValue;
        addMsg(`Welcome to ${modeText}! How can I help?`, "assistant");
      }
    }

    currentChatMode = modeValue;
  }
}

// ✅ FIX 1: Auto Scroll — smooth sub-pixel scrolling with rAF
function startAutoScroll() {
  const wrapper = document.querySelector(".cards-wrapper");
  if (!shouldAutoScrollCarousel(wrapper)) return;
  stopAutoScroll();

  let exactScrollLeft = wrapper.scrollLeft;

  function smoothScroll() {
    if (!shouldAutoScrollCarousel(wrapper)) {
      stopAutoScroll();
      return;
    }

    // Sync if user manually scrolled
    if (Math.abs(exactScrollLeft - wrapper.scrollLeft) > 2) {
      exactScrollLeft = wrapper.scrollLeft;
    }

    exactScrollLeft += AUTO_SCROLL_SPEED;
    wrapper.scrollLeft = exactScrollLeft;

    if (wrapper.scrollLeft + wrapper.clientWidth >= wrapper.scrollWidth - 2) {
      wrapper.scrollLeft = 0;
      exactScrollLeft = 0;
    }

    autoScrollInterval = requestAnimationFrame(smoothScroll);
  }

  autoScrollInterval = requestAnimationFrame(smoothScroll);
}

function stopAutoScroll() {
  if (autoScrollInterval) {
    cancelAnimationFrame(autoScrollInterval);
    autoScrollInterval = null;
  }
}

document.addEventListener("visibilitychange", () => {
  syncBackgroundVideoPlayback();
  syncVoiceVideoPlayback();

  if (document.hidden) {
    stopAutoScroll();
    return;
  }

  startAutoScroll();
});

function applyMovieCardTilt(card) {
  if (!card || card.dataset.cardTiltBound === "true") return;
  card.dataset.cardTiltBound = "true";

  let shine = card.querySelector(".card-shine");
  if (!shine) {
    shine = document.createElement("div");
    shine.className = "card-shine";
    card.appendChild(shine);
  }

  const state = {
    rect: null,
    frame: null,
    x: 0,
    y: 0,
  };

  const updateRect = () => {
    state.rect = card.getBoundingClientRect();
  };

  const renderTilt = () => {
    state.frame = null;
    if (!state.rect) return;

    const centerX = state.rect.width / 2;
    const centerY = state.rect.height / 2;
    const rotateX = ((state.y - centerY) / centerY) * -12;
    const rotateY = ((state.x - centerX) / centerX) * 12;

    card.style.transform = `perspective(800px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale(1.05)`;
    shine.style.opacity = "1";
    shine.style.background = `linear-gradient(${135 + rotateY * 2}deg, rgba(255,255,255,0.3) 0%, rgba(255,255,255,0) 60%)`;
  };

  card.addEventListener("pointerenter", updateRect, { passive: true });
  card.addEventListener(
    "pointermove",
    (event) => {
      if (window.innerWidth <= 768 || prefersReducedMotion()) return;
      if (!state.rect) {
        updateRect();
      }
      if (!state.rect) return;

      state.x = event.clientX - state.rect.left;
      state.y = event.clientY - state.rect.top;

      if (state.frame !== null) return;
      state.frame = requestAnimationFrame(renderTilt);
    },
    { passive: true },
  );
  card.addEventListener("pointerleave", () => {
    if (state.frame !== null) {
      cancelAnimationFrame(state.frame);
      state.frame = null;
    }
    state.rect = null;
    card.style.transform = "perspective(800px) rotateX(0) rotateY(0) scale(1)";
    shine.style.opacity = "0";
  });
}

function addTiltEffect() {
  if (window.innerWidth <= 768 || prefersReducedMotion()) return;
  document.querySelectorAll(".movie-card-placeholder").forEach(applyMovieCardTilt);
}

function createMovieCardElement(movie, index) {
  const card = document.createElement("div");
  const posterUrl = movie.poster_path
    ? `https://image.tmdb.org/t/p/w342${movie.poster_path}`
    : "https://via.placeholder.com/342x513?text=No+Poster";
  const rating = movie.vote_average ? movie.vote_average.toFixed(1) : "N/A";
  const year = movie.release_date ? movie.release_date.substring(0, 4) : "";

  card.className = "movie-card-placeholder";
  card.dataset.movieIndex = String(index);
  card.innerHTML = `
    <img src="${posterUrl}" alt="${movie.title}" loading="lazy" decoding="async" onerror="this.src='https://via.placeholder.com/342x513?text=Error'">
    <div class="card-rating-badge">â­ ${rating}</div>
    <div class="card-overlay">
      <div class="card-overlay-content">
        <span class="card-text">${movie.title}</span>
        ${year ? `<span class="card-year">${year}</span>` : ""}
      </div>
    </div>
  `;

  return card;
}

function renderTrendingMovies(results) {
  const container = document.getElementById("cards-container");
  if (!container) return;

  const renderToken = ++trendingRenderToken;
  currentMovies = results;
  container.textContent = "";
  container.scrollLeft = 0;
  bindMovieCarouselInteractions(container);

  const cardsHTML = results
    .map((m, index) => {
      const posterUrl = m.poster_path
        ? `https://image.tmdb.org/t/p/w342${m.poster_path}`
        : "https://via.placeholder.com/342x513?text=No+Poster";
      const rating = m.vote_average ? m.vote_average.toFixed(1) : 'N/A';
      const year = m.release_date ? m.release_date.substring(0, 4) : '';
      return `<div class="movie-card-placeholder" data-movie-index="${index}">
        <img src="${posterUrl}" alt="${m.title}" loading="lazy" decoding="async" onerror="this.src='https://via.placeholder.com/342x513?text=Error'">
        <div class="card-rating-badge">⭐ ${rating}</div>
        <div class="card-overlay">
          <div class="card-overlay-content">
            <span class="card-text">${m.title}</span>
            ${year ? `<span class="card-year">${year}</span>` : ''}
          </div>
        </div>
      </div>`;
    })
    .join("");

  container.innerHTML = cardsHTML;

  const cards = Array.from(container.querySelectorAll(".movie-card-placeholder"));
  const animatedCards = prefersReducedMotion()
    ? []
    : cards.slice(0, MAX_GSAP_CARD_ANIMATIONS);

  if (animatedCards.length > 0) {
    gsap.fromTo(
      animatedCards,
      { opacity: 0, y: 30, scale: 0.92 },
      {
        opacity: 1,
        y: 0,
        scale: 1,
        duration: 0.45,
        ease: "power3.out",
        stagger: 0.055,
        clearProps: "transform",
      },
    );
  }

  scheduleIdleTask(() => {
    if (renderToken !== trendingRenderToken) return;
    addTiltEffect();
    startAutoScroll();
  }, 200);
}

async function loadTrendingMovies(forceRefresh = false) {
  const container = document.getElementById("cards-container");
  if (!container) return;

  stopAutoScroll();

  const tmdbKey = readStorage("tmdbKey");
  if (!tmdbKey) {
    container.innerHTML = `<div class="card-text" style="padding: 20px;">Please set TMDB API Key in settings.</div>`;
    return;
  }

  const cacheIsFresh =
    !forceRefresh &&
    cachedTrendingKey === tmdbKey &&
    cachedTrendingMovies.length > 0 &&
    Date.now() - cachedTrendingAt < MOVIE_CACHE_TTL_MS;

  if (cacheIsFresh) {
    renderTrendingMovies(cachedTrendingMovies);
    return;
  }

  if (trendingMoviesRequest && !forceRefresh) {
    container.innerHTML =
      '<div class="card-text" style="padding: 20px;">Loading trending...</div>';
    try {
      const data = await trendingMoviesRequest;
      if (data.results && data.results.length > 0) {
        renderTrendingMovies(data.results);
      }
    } catch (e) {
      container.innerHTML =
        '<div class="card-text" style="color:red;">Error fetching TMDB. Check connection/key.</div>';
    }
    return;
  }

  container.innerHTML =
    '<div class="card-text" style="padding: 20px;">Loading trending...</div>';

  try {
    trendingMoviesRequest = fetch(
      `https://api.themoviedb.org/3/trending/movie/week?api_key=${tmdbKey}`,
    ).then((res) => res.json());

    const data = await trendingMoviesRequest;
    if (data.results && data.results.length > 0) {
      cachedTrendingMovies = data.results;
      cachedTrendingAt = Date.now();
      cachedTrendingKey = tmdbKey;
      renderTrendingMovies(data.results);
    } else {
      container.innerHTML =
        '<div class="card-text">No trending info available.</div>';
    }
  } catch (e) {
    container.innerHTML =
      '<div class="card-text" style="color:red;">Error fetching TMDB. Check connection/key.</div>';
  } finally {
    trendingMoviesRequest = null;
  }
}

// 🔊 Toggle Video sound logic
function toggleVideoSound() {
  const bgVid = document.getElementById('bg-video');
  const soundToggle = document.getElementById('soundToggle');
  if (!bgVid || !soundToggle || soundToggle.disabled) return;

  bgVid.muted = !bgVid.muted;
  setSoundToggleState(bgVid.muted);

  if (!bgVid.muted && bgVid.paused) {
    playInlineVideo(bgVid);
  }
}

async function openMovieDetails(index, event) {
  if (event) event.stopPropagation();
  if (inputMode === "voice" || document.body.classList.contains("voice-mode-active")) return;

  const movie = currentMovies[index];

  document.body.classList.add("movie-chat-active");

  const poster = movie.poster_path
    ? `https://image.tmdb.org/t/p/w500${movie.poster_path}`
    : null;
  const year = movie.release_date
    ? new Date(movie.release_date).getFullYear()
    : "N/A";
  const rating = movie.vote_average ? movie.vote_average.toFixed(1) : 'N/A';

  // Build star display
  const starCount = Math.round((movie.vote_average || 0) / 2);
  const stars = '&#9733;'.repeat(starCount) + '&#9734;'.repeat(5 - starCount);

  // Try to get detailed info from backend
  let genres = '';
  let director = '';
  let runtime = '';
  let trailerBtn = '';
  let recsHTML = '';

  try {
    const tmdbKey = readStorage("tmdbKey");
    if (tmdbKey) {
      const detailRes = await fetch(
        `https://api.themoviedb.org/3/movie/${movie.id}?api_key=${tmdbKey}&append_to_response=credits,videos,recommendations`
      );
      const detail = await detailRes.json();

      // Genres
      if (detail.genres && detail.genres.length > 0) {
        genres = detail.genres.slice(0, 4).map(g =>
          `<span class="movie-genre-tag">${g.name}</span>`
        ).join('');
        genres = `<div class="movie-detail-genres">${genres}</div>`;
      }

      // Director
      const crew = detail.credits?.crew || [];
      const dir = crew.find(c => c.job === 'Director');
      if (dir) director = `<div class="movie-detail-director">Directed by <strong>${dir.name}</strong></div>`;

      // Runtime
      if (detail.runtime) {
        const h = Math.floor(detail.runtime / 60);
        const m = detail.runtime % 60;
        runtime = `<span class="movie-detail-runtime">⏱️ ${h}h ${m}m</span>`;
      }

      // Trailer
      const videos = detail.videos?.results || [];
      const trailer = videos.find(v => v.type === 'Trailer' && v.site === 'YouTube');
      if (trailer) {
        trailerBtn = `<a href="https://www.youtube.com/watch?v=${trailer.key}" target="_blank" class="movie-trailer-btn">Watch trailer</a>`;
      }

      // Recommendations
      const recs = detail.recommendations?.results?.slice(0, 5) || [];
      if (recs.length > 0) {
        const recCards = recs.map(r => {
          const rp = r.poster_path ? `https://image.tmdb.org/t/p/w200${r.poster_path}` : '';
          const rr = r.vote_average ? r.vote_average.toFixed(1) : '';
          return rp ? `<div class="rec-card">
            <img src="${rp}" alt="${r.title}" loading="lazy">
            <div class="rec-info">
              <span class="rec-title">${r.title}</span>
              ${rr ? `<span class="rec-rating">⭐ ${rr}</span>` : ''}
            </div>
          </div>` : '';
        }).filter(Boolean).join('');
        if (recCards) {
          recsHTML = `<div class="movie-recs-section">
            <div class="movie-recs-label">Similar Movies</div>
            <div class="movie-recs-row">${recCards}</div>
          </div>`;
        }
      }
    }
  } catch (e) {
    console.log("Movie detail fetch error:", e);
  }

  const summariseId = `summarise-result-${Date.now()}`;

  const summariseBtn = `<button class="movie-summarise-btn" onclick="summariseMovie('${movie.title.replace(/'/g, "\\'")}', '${(movie.overview || '').replace(/'/g, "\\'")}', '${summariseId}')">Summarize</button>`;
  const summariseArea = `<div id="${summariseId}" class="movie-summary-result" style="display:none;"></div>`;

  const msgHtml = `<div class="movie-detail-card">
    <div class="movie-detail-title">${movie.title}</div>
    ${genres}
    <div class="movie-detail-meta">
      <span class="movie-detail-year">${year}</span>
      <span class="movie-detail-rating">${stars} ${rating}/10</span>
      ${runtime}
    </div>
    ${director}
    <div class="movie-detail-overview">${movie.overview}</div>
    ${summariseBtn}
    ${summariseArea}
    ${trailerBtn}
    ${recsHTML}
  </div>`;

  addMsg(msgHtml, "assistant", poster, "0s");
}

async function summariseMovie(title, overview, resultId) {
  const resultBox = document.getElementById(resultId);
  if (!resultBox) return;

  // If already showing summary, toggle it off
  if (resultBox.style.display === 'block' && resultBox.dataset.loaded === 'true') {
    resultBox.style.display = 'none';
    return;
  }

  // Show loading state
  resultBox.style.display = 'block';
  resultBox.innerHTML = `<div class="summary-loading"><span class="summary-shimmer"></span> Generating summary...</div>`;

  try {
    const res = await fetch('/movie-summarise', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-NEON-KEY': 'NEON_LOCAL_SECRET'
      },
      body: JSON.stringify({ title, overview })
    });

    const data = await res.json();

    if (data.error) {
      resultBox.innerHTML = `<div class="summary-error">⚠️ ${data.error}</div>`;
    } else {
      resultBox.dataset.loaded = 'true';
      resultBox.innerHTML = `
        <div class="summary-header">📝 AI Summary</div>
        <div class="summary-text">${renderMessage(data.summary)}</div>
      `;
    }
  } catch (e) {
    console.error('Summarise error:', e);
    resultBox.innerHTML = `<div class="summary-error">⚠️ Failed to generate summary. Check server.</div>`;
  }
}

const _carousel = document.getElementById("movie-carousel");
if (_carousel) {
  _carousel.addEventListener("click", () => {
    const isMobile = window.innerWidth <= 768;
    if (isMobile) return;

    const input = document.getElementById("userInput");
    if (document.activeElement === input) {
      input.blur();
      return;
    }

    document.body.classList.remove("movie-chat-active");

    _carousel.style.willChange = "transform, opacity";
    gsap.to(_carousel, {
      scale: 1,
      opacity: 1,
      duration: 0.5,
      ease: "back.out(1.4)",
      // ✅ FIX 2: Only clear transform & opacity, not display
      clearProps: "transform,opacity",
      onComplete: () => {
        _carousel.style.willChange = "auto";
      },
    });
  });
}

const userInputField = document.getElementById("userInput");
const movieCarousel = document.getElementById("movie-carousel");

if (userInputField) {
  userInputField.addEventListener("focus", () => {
    const isMobile = window.innerWidth <= 768;
    document.body.classList.add("movie-chat-active");

    gsap.to(userInputField, {
      scale: 1.02,
      boxShadow: "0 0 10px var(--primary-glow, rgba(0, 255, 255, 0.15))",
      borderColor: "var(--primary-glow, #0ff)",
      duration: 0.3,
    });

    if (movieCarousel && !isMobile) {
      movieCarousel.style.willChange = "transform, opacity";
      gsap.to(movieCarousel, {
        scale: 0.92,
        opacity: 0.4,
        duration: 0.5,
        ease: "power2.inOut",
      });
    }
  });

  userInputField.addEventListener("blur", () => {
    const isMobile = window.innerWidth <= 768;

    document.body.classList.remove("movie-chat-active");

    gsap.to(userInputField, {
      scale: 1,
      boxShadow: "inset 0 2px 5px rgba(0,0,0,0.2)",
      borderColor: "rgba(255,255,255,0.15)",
      duration: 0.3,
    });

    if (movieCarousel && !isMobile) {
      gsap.to(movieCarousel, {
        scale: 1,
        opacity: 1,
        duration: 0.5,
        ease: "back.out(1.4)",
        // ✅ FIX 3: Only clear transform & opacity, not all (fixes display:none bug)
        clearProps: "transform,opacity",
        onComplete: () => {
          movieCarousel.style.willChange = "auto";
        },
      });
    }
  });
}

async function appendTextWithBatching(textNode, text, chatContainer) {
  const chunkSize = text.length > 600 ? 24 : text.length > 240 ? 12 : 4;
  let index = 0;
  let lastScrollIndex = 0;

  while (index < text.length) {
    let buffer = "";
    const frameStart = performance.now();

    while (index < text.length && performance.now() - frameStart < 8) {
      buffer += text.slice(index, index + chunkSize);
      index += chunkSize;
    }

    if (buffer) {
      textNode.textContent += buffer;
      if (index - lastScrollIndex >= chunkSize * 8 || index >= text.length) {
        scheduleChatScroll(chatContainer);
        lastScrollIndex = index;
      }
    }

    if (index < text.length) {
      await nextAnimationFrame();
    }
  }
}

async function typeWriter(element, html) {
  if (!element) return;

  if (prefersReducedMotion() || html.length > 1800) {
    element.innerHTML = html;
    scheduleChatScroll(document.getElementById("chat-container"));
    return;
  }

  const tempDiv = document.createElement("div");
  tempDiv.innerHTML = html;

  element.innerHTML = "";
  const chatContainer = document.getElementById("chat-container");

  const cursor = document.createElement("span");
  cursor.className = "cursor-blink";
  element.appendChild(cursor);

  async function typeNode(node, target) {
    if (node.nodeType === Node.TEXT_NODE) {
      const text = node.textContent;

      const isCodeBlock =
        target.closest("pre") ||
        target.closest("code") ||
        target.classList.contains("instant-type");

      if (isCodeBlock) {
        target.insertBefore(document.createTextNode(text), cursor);
        scheduleChatScroll(chatContainer);
      } else {
        const textNode = document.createTextNode("");
        target.insertBefore(textNode, cursor);
        await appendTextWithBatching(textNode, text, chatContainer);
      }
    } else if (node.nodeType === Node.ELEMENT_NODE) {
      const newNode = document.createElement(node.tagName);
      Array.from(node.attributes).forEach((attr) => {
        newNode.setAttribute(attr.name, attr.value);
      });
      target.insertBefore(newNode, cursor);

      if (!["BR", "HR", "IMG", "INPUT"].includes(node.tagName)) {
        for (const child of Array.from(node.childNodes)) {
          await typeNode(child, newNode);
        }
      }
    }
  }

  try {
    for (const child of Array.from(tempDiv.childNodes)) {
      await typeNode(child, element);
    }
  } catch (err) {
    console.error("Typewriter error:", err);
    element.innerHTML = html;
  } finally {
    if (cursor && cursor.parentNode) cursor.remove();
    scheduleChatScroll(chatContainer);
  }
}

async function sendMessage() {
  const input = document.getElementById("userInput");
  const modeSelect = document.getElementById("modeSelect");
  if (!input || !modeSelect) return;

  const text = input.value.trim();
  const mode = modeSelect.value;

  if (!text && !pendingChatImage) return;

  const sendBtn =
    input.nextElementSibling || input.parentElement.querySelector("button");
  if (sendBtn) {
    const icon =
      sendBtn.querySelector("svg") ||
      sendBtn.querySelector("i") ||
      sendBtn.querySelector(".send-icon-anim");
    if (icon) {
      icon.classList.remove("fly-away");
      void icon.offsetWidth;
      icon.classList.add("fly-away");
    }
  }

  if (pendingChatImage) {
    const blobUrl = URL.createObjectURL(pendingChatImage);
    const imgHtml = `<img src="${blobUrl}" style="max-width: 200px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.1); margin-bottom: 8px; display: block;" alt="User Uploaded Image" />`;
    addMsg(imgHtml + (text ? text : ""), "user");
    // Visually hide the preview box immediately
    const previewContainer = document.getElementById("chat-image-preview-container");
    if (previewContainer) previewContainer.style.display = "none";
  } else {
    addMsg(text, "user");
  }

  input.value = "";
  setThinkingState(true);

  // 🎮 Easter eggs (chat-only, local UI)
  const egg = detectEasterEgg(text);
  if (egg) {
    setThinkingState(false);
    triggerEasterEgg(egg);
    return;
  }

  if (text.toLowerCase() === "show demo poster") {
    setTimeout(() => {
      setThinkingState(false);
      addMsg(
        "Here is a demo poster for testing.",
        "assistant",
        "https://image.tmdb.org/t/p/w500/qJ2tW6WMUDux911r6m7haRef0WH.jpg",
      );
    }, 1500);
    return;
  }

  const startTime = performance.now();

  try {
    let res;
    
    // 📸 If an image is attached, we route to the vision endpoint
    if (pendingChatImage) {
      const reader = new FileReader();
      const base64Promise = new Promise((resolve) => {
        reader.onload = (e) => resolve(e.target.result);
        reader.readAsDataURL(pendingChatImage);
      });
      
      const base64Data = await base64Promise;
      
      res = await fetch("/api/analyze-image", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image: base64Data,
          query: text,
          file_type: "image",
        }),
      });
      
      // Clear the pending image
      pendingChatImage = null;
      document.getElementById("userInput").placeholder = "Type command...";
    } else {
      // 💬 Standard text chat
      res = await fetch("/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-NEON-KEY": "NEON_LOCAL_SECRET"
        },
        body: JSON.stringify({
          message: text,
          mode: mode,
        }),
      });
    }

    const data = await res.json();
    setThinkingState(false);

    const endTime = performance.now();
    const latency = ((endTime - startTime) / 1000).toFixed(2) + "s";

    if (data.error) {
      addMsg("Error: " + data.error, "assistant", null, latency);
    } else if (data.movie_data) {
      // 🎬 Render rich movie card with Summarise button
      const md = data.movie_data;
      const poster = md.poster || null;
      const year = md.year || 'N/A';
      const rating = md.rating || 'N/A';
      const starCount = Math.round((typeof md.rating === 'number' ? md.rating : 0) / 2);
      const stars = '&#9733;'.repeat(starCount) + '&#9734;'.repeat(5 - starCount);

      let genres = '';
      if (md.genres) {
        const genreArr = md.genres.split(', ');
        genres = `<div class="movie-detail-genres">${genreArr.map(g => `<span class="movie-genre-tag">${g}</span>`).join('')}</div>`;
      }

      let director = md.director ? `<div class="movie-detail-director">Directed by <strong>${md.director}</strong></div>` : '';
      let runtime = md.runtime && md.runtime !== 'N/A' ? `<span class="movie-detail-runtime">${md.runtime}</span>` : '';
      let cast = md.cast ? `<div style="font-size:0.8rem;color:rgba(255,255,255,0.6);font-family:Poppins,sans-serif;">Cast: ${md.cast}</div>` : '';
      let overview = md.plot || 'No description available.';

      let trailerBtn = md.trailer ? `<a href="${md.trailer}" target="_blank" class="movie-trailer-btn">Watch trailer</a>` : '';

      let recsHTML = '';
      if (md.recommendations && md.recommendations.length > 0) {
        const recCards = md.recommendations.map(r => {
          return r.poster ? `<div class="rec-card">
            <img src="${r.poster}" alt="${r.title}" loading="lazy">
            <div class="rec-info">
              <span class="rec-title">${r.title}</span>
                ${r.rating ? `<span class="rec-rating">Rating ${r.rating}</span>` : ''}
            </div>
          </div>` : '';
        }).filter(Boolean).join('');
        if (recCards) {
          recsHTML = `<div class="movie-recs-section">
            <div class="movie-recs-label">Similar Movies</div>
            <div class="movie-recs-row">${recCards}</div>
          </div>`;
        }
      }

      const sumId = `summarise-result-${Date.now()}`;
      const safeTitle = (md.title || '').replace(/'/g, "\\'");
      const safeOverview = (overview || '').replace(/'/g, "\\'");
      const summariseBtn = `<button class="movie-summarise-btn" onclick="summariseMovie('${safeTitle}', '${safeOverview}', '${sumId}')">Summarize</button>`;
      const summariseArea = `<div id="${sumId}" class="movie-summary-result" style="display:none;"></div>`;

      const movieCardHtml = `<div class="movie-detail-card">
        <div class="movie-detail-title">${md.title || 'Unknown'}</div>
        ${genres}
        <div class="movie-detail-meta">
          <span class="movie-detail-year">${year}</span>
          <span class="movie-detail-rating">${stars} ${rating}/10</span>
          ${runtime}
        </div>
        ${director}
        ${cast}
        <div class="movie-detail-overview">${overview}</div>
        ${summariseBtn}
        ${summariseArea}
        ${trailerBtn}
        ${recsHTML}
      </div>`;

      addMsg(movieCardHtml, "assistant", poster, latency, data.sources || null, null);
    } else {
      addMsg(
        data.response || "No response.",
        "assistant",
        data.poster_url,
        latency,
        data.sources || null,
        data.confidence != null ? {
          score: data.confidence,
          label: data.confidence_label,
          emoji: data.confidence_emoji
        } : null
      );
    }
  } catch (e) {
    setThinkingState(false);
    console.error("Chat Error:", e);
    addMsg("Connection failed. Check server.", "assistant");
  }
}

function detectEasterEgg(text) {
  if (!text) return null;
  const t = text.trim().toLowerCase();
  if (t === "/re9" || t.includes("resident evil 9") || t.includes("re9")) return "re9";
  if (t === "/wuwa" || t.includes("wuthering waves") || t.includes("wuwa")) return "wuwa";
  return null;
}

function triggerEasterEgg(kind) {
  const body = document.body;
  if (!body) return;

  const cls = kind === "re9" ? "egg-re9" : "egg-wuwa";
  body.classList.add(cls);

  if (kind === "re9") {
    addMsg(
      "Access granted. RE9 protocol online. If you hear footsteps... don't look back.",
      "assistant",
    );
  } else {
    addMsg(
      "WUWA resonance detected. Calibrating waves... stay sharp, Rover.",
      "assistant",
    );
  }

  setTimeout(() => body.classList.remove(cls), 4500);
}

function copyCodeBlock(blockId) {
  const block = document.getElementById(blockId);
  if (!block) return;
  const code = block.querySelector("code");
  if (!code) return;

  const text = code.innerText;
  navigator.clipboard.writeText(text).then(() => {
    const btn = block.querySelector(".code-copy-btn");
    if (btn) {
      btn.innerHTML = '<span class="copy-icon">✓</span> Copied!';
      btn.classList.add("copied");
      setTimeout(() => {
        btn.innerHTML = '<span class="copy-icon">📋</span> Copy';
        btn.classList.remove("copied");
      }, 2000);
    }
  }).catch(() => {
    // Fallback for older browsers
    const textarea = document.createElement("textarea");
    textarea.value = text;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    document.body.removeChild(textarea);
  });
}

function renderMessage(text) {
  if (!text) return "";

  text = text.replace(/\\n/g, "\n");

  const placeholders = [];

  // Code blocks (preserve first)
  text = text.replace(/```(\w+)?\s*([\s\S]*?)```/g, (_, lang, code) => {
    const safeCode = code
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    const blockId = `code-block-${Date.now()}-${placeholders.length}`;
    const langLabel = lang ? `<span class="code-lang-label">${lang}</span>` : '';
    const placeholder = `__CODE_BLOCK_${placeholders.length}__`;

    const html = `
      <div class="code-block" id="${blockId}">
        <div class="code-header">
          ${langLabel}
          <button class="code-copy-btn" onclick="copyCodeBlock('${blockId}')" title="Copy code">
            <span class="copy-icon">📋</span> Copy
          </button>
        </div>
        <pre class="instant-type"><code>${safeCode}</code></pre>
      </div>`;
    placeholders.push(html);
    return placeholder;
  });

  // Inline code
  text = text.replace(
    /`([^`]+)`/g,
    '<span class="inline-code">$1</span>',
  );

  // Markdown bold and italic
  text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  text = text.replace(/\*(.+?)\*/g, '<em>$1</em>');

  // Headers (## and ###)
  text = text.replace(/^###\s+(.+)$/gm, '<div class="render-h3">$1</div>');
  text = text.replace(/^##\s+(.+)$/gm, '<div class="render-h2">$1</div>');

  // Horizontal rules
  text = text.replace(/^---+$/gm, '<div class="render-hr"></div>');

  // Numbered lists (1. 2. 3.)
  text = text.replace(/^(\d+)\.\s+(.+?)(?:\s*-\s*(.+))?$/gm, (_, num, title, desc) => {
    if (desc) {
      return `<div class="render-list-item"><span class="render-list-num">${num}</span><div class="render-list-content"><strong>${title}</strong><span class="render-list-desc">${desc}</span></div></div>`;
    }
    return `<div class="render-list-item"><span class="render-list-num">${num}</span><div class="render-list-content">${title}</div></div>`;
  });

  // Bullet points (- item)
  text = text.replace(/^[-•]\s+(.+)$/gm, '<div class="render-bullet"><span class="render-bullet-dot">›</span>$1</div>');

  // Rating line
  text = text.replace(/Rating:\s*(⭐[\d.]+)/g, '<div class="render-rating">$1</div>');

  // Convert remaining newlines
  text = text.replace(/(?:\r\n|\r|\n)/g, "<br>");

  // Clean up excessive breaks around block elements
  text = text.replace(/<br>\s*(<div class="render-)/g, '$1');
  text = text.replace(/(<\/div>)\s*<br>/g, '$1');

  // Style YouTube links as music-link cards or inline players
  text = text.replace(
    /\[([^\]]*(?:Play|YouTube|Listen|Lyrics|▶️|Greatest|Top Songs|Latest)[^\]]*)\]\((https:\/\/(?:www\.)?youtube\.com\/[^)]+)\)/g,
    (match, label, url) => {
      const vidMatch = url.match(/watch\?v=([\w-]+)/);
      if (vidMatch) {
        return `<div style="margin: 8px 0; border-radius: 12px; overflow: hidden; max-width: 320px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); border: 1px solid rgba(255,50,50,0.2);">
          <iframe width="100%" height="160" src="https://www.youtube.com/embed/${vidMatch[1]}?autoplay=0" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen style="display:block;"></iframe>
        </div>`;
      }
      return `<a href="${url}" target="_blank" rel="noopener" class="music-link">${label}</a>`;
    }
  );

  // Restore code blocks
  placeholders.forEach((html, index) => {
    text = text.replace(`__CODE_BLOCK_${index}__`, html);
  });

  return text;
}

function addMsg(text, type, posterUrl = null, latency = null, sources = null, confidenceData = null) {
  const chatContainer = document.getElementById("chat-container");
  if (!chatContainer) return;

  // Get or create the mode-specific wrapper
  const container = getOrCreateModeContainer(currentChatMode);
  if (!container) return;
  container.style.display = "block";

  const rowDiv = document.createElement("div");
  rowDiv.className = `chat-row ${type}`;

  let avatarHTML = "";
  let nameTag = "";

  if (type === "user") {
    const storedPic = getUserAvatar();
    const userNameField = document.getElementById("userName");
    const storedName = userNameField ? userNameField.value || "User" : "User";
    nameTag = `<div class="chat-name-tag user-name-label">${storedName}</div>`;
    avatarHTML = `<div class="user-avatar-glow"></div><img src="${storedPic}" class="chat-avatar-img chat-user-pic">`;
  } else {
    nameTag = `<div class="chat-name-tag">Neon AI</div>`;
    avatarHTML = `<div class="ai-avatar-multiglow"></div><div class="ai-n-logo">N</div>`;
  }

  if (!posterUrl) {
    const urlRegex =
      /(https?:\/\/[^\s]+?\.(jpg|jpeg|png|gif|webp)(\?[^\s]+)?)/i;
    const match = text.match(urlRegex);
    if (match) {
      posterUrl = match[0];
      text = text.replace(match[0], "").trim();
    }
  }

  let cleanText = text;
  if (posterUrl && posterUrl !== "null") {
    cleanText = cleanText.replace(posterUrl, "").trim();
  }

  let messageContent = renderMessage(cleanText);
  let extraContent = "";

  if (posterUrl && posterUrl !== "null" && posterUrl !== "undefined") {
    extraContent = `<br><img src="${posterUrl}" class="chat-poster" alt="Movie Poster" loading="lazy">`;
  }

  // Build source pills HTML (favicon icons for web sources)
  let sourcesHTML = "";
  if (sources && sources.length > 0) {
    const pills = sources.map(s => {
      const favicon = `https://www.google.com/s2/favicons?domain=${s.domain}&sz=32`;
      return `<a href="${s.url}" target="_blank" rel="noopener" class="source-pill" title="${s.domain}">
        <img src="${favicon}" alt="${s.domain}" class="source-favicon">
        <span class="source-domain">${s.domain.split('.').slice(-2, -1)[0] || s.domain}</span>
      </a>`;
    }).join("");
    sourcesHTML = `<div class="source-pills-row"><span class="source-label">🌐</span>${pills}</div>`;
  }

  let metaInfo = "";
  if (latency || confidenceData) {
    let confTag = "";
    if (confidenceData) {
      let confColor = confidenceData.score >= 75 ? "#00e5a0" : (confidenceData.score >= 55 ? "#ffc107" : "#ff4444");
      confTag = `<span class="confidence-badge" style="color: ${confColor}; border-color: ${confColor}; margin-right: 8px;">
        ${confidenceData.score}%
      </span>`;
    }
    metaInfo = `<div style="font-size: 0.7rem; opacity: 0.5; margin-top: 5px; text-align: right; display: flex; justify-content: flex-end; align-items: center;">
      ${confTag}
      ${latency ? `⚡ ${latency}` : ''}
    </div>`;
  }

  rowDiv.innerHTML = `<div class="chat-avatar-container">${avatarHTML}</div><div class="msg-column">${nameTag}<div class="msg"></div>${sourcesHTML}${metaInfo}</div>`;

  container.appendChild(rowDiv);

  // ✅ Apply 3D effect to newly added AI logo in chat
  if (type === "assistant") {
    const newLogo = rowDiv.querySelector(".ai-n-logo");
    if (newLogo) apply3DIconEffect(newLogo);
  }

  const msgDiv = rowDiv.querySelector(".msg");

  if (type === "assistant" && !posterUrl) {
    typeWriter(msgDiv, messageContent + extraContent);
  } else {
    msgDiv.innerHTML = messageContent + extraContent;
  }

  requestAnimationFrame(() => {
    const scrollTarget = document.getElementById("chat-container");
    scheduleChatScroll(scrollTarget);
  });
}

async function saveAllKeys() {
  const apiKeyInput = document.getElementById("apiKeyInput");
  const tmdbKeyInput = document.getElementById("tmdbKeyInput");

  const tKey = apiKeyInput ? apiKeyInput.value.trim() : "";
  const mKey = tmdbKeyInput ? tmdbKeyInput.value.trim() : "";

  setThinkingState(true);
  if (mKey) writeStorage("tmdbKey", mKey);
  cachedTrendingMovies = [];
  cachedTrendingAt = 0;
  cachedTrendingKey = "";
  if (tKey)
    await fetch("/set-api-key", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: tKey }),
    });
  if (mKey)
    await fetch("/set-tmdb-key", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: mKey }),
    });
  setThinkingState(false);
  addMsg("Keys Updated (Trending Now Active).", "assistant");

  const modeSelect = document.getElementById("modeSelect");
  if (modeSelect && modeSelect.value === "movie") loadTrendingMovies();
}

async function removeAllKeys() {
  if (!confirm("Remove all API keys?")) return;
  removeStorage("tmdbKey");
  cachedTrendingMovies = [];
  cachedTrendingAt = 0;
  cachedTrendingKey = "";
  await fetch("/set-api-key", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: "" }),
  });
  await fetch("/set-tmdb-key", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: "" }),
  });
  const apiKeyInput = document.getElementById("apiKeyInput");
  const tmdbKeyInput = document.getElementById("tmdbKeyInput");
  if (apiKeyInput) apiKeyInput.value = "";
  if (tmdbKeyInput) tmdbKeyInput.value = "";
  addMsg("Keys Removed. Offline Mode.", "assistant");
  loadTrendingMovies();
}

async function uploadPDF() {
  const fileInput = document.getElementById("pdfFile");
  if (!fileInput || !fileInput.files[0]) return;

  const fileNameDisplay = document.getElementById("fileNameDisplay");
  if (fileNameDisplay) fileNameDisplay.innerText = fileInput.files[0].name;

  addMsg(`Uploading PDF...`, "assistant");
  setThinkingState(true);
  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  try {
    const res = await fetch("/upload-pdf", { method: "POST", body: formData });
    const data = await res.json();
    setThinkingState(false);
    addMsg(
      data.status === "success" ? "PDF Indexed!" : "Error: " + data.message,
      "assistant",
    );
  } catch (e) {
    setThinkingState(false);
  }
}

async function deletePDF() {
  const res = await fetch("/delete-pdf", { method: "POST" });
  const data = await res.json();
  addMsg(data.status === "success" ? "PDF Deleted." : "Error.", "assistant");
}

async function resetExamDB() {
  if (!confirm("Reset Exam Memory?")) return;
  const res = await fetch("/reset-exam-db", { method: "POST" });
  const data = await res.json();
  addMsg(data.status === "success" ? "Database Reset." : "Error.", "assistant");
}

function handleEnter(e) {
  if (e.key === "Enter") {
    e.preventDefault();
    sendMessage();
  }
}

// ==========================================
// 🎙️ VOICE MODE & AUDIO RECORDING LOGIC
// ==========================================

let inputMode = "chat";
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;

function activateVoiceMode() {
  inputMode = "voice";
  document.body.classList.add("voice-mode-active");

  // Prevent movie cards from showing or scrolling in background
  document.body.classList.remove("movie-chat-active");
  stopAutoScroll();

  const toggleBtn = document.getElementById("voice-mode-toggle");
  if (toggleBtn) {
    setVoiceToggleContent(toggleBtn, true);
    toggleBtn.classList.add("voice-active");
  }
}

function deactivateVoiceMode() {
  inputMode = "chat";
  document.body.classList.remove("voice-mode-active");
  const toggleBtn = document.getElementById("voice-mode-toggle");
  if (toggleBtn) {
    setVoiceToggleContent(toggleBtn, false);
    toggleBtn.classList.remove("voice-active");
  }
}

function initVoiceMode() {
  const inputBox = document.querySelector('.input-box');
  if (!inputBox) return;

  // ==========================================
  // VOICE UI CONTAINER — Premium Layout
  // ==========================================
  const voiceUI = document.createElement("div");
  voiceUI.id = "voice-ui-container";
  voiceUI.addEventListener("click", e => e.stopPropagation());

  // 🎨 Wallpaper Background Layer (inside the voice popup)
  const voiceBg = document.createElement("div");
  voiceBg.className = "voice-bg-layer";
  voiceUI.appendChild(voiceBg);

  // ✨ Floating Particles inside voice popup
  const voiceParticles = document.createElement("div");
  voiceParticles.className = "voice-particles";
  for (let i = 0; i < 15; i++) {
    const p = document.createElement("div");
    p.className = "voice-particle";
    p.style.left = Math.random() * 100 + "%";
    p.style.top = (20 + Math.random() * 60) + "%";
    p.style.animationDelay = (Math.random() * 4) + "s";
    p.style.animationDuration = (3 + Math.random() * 3) + "s";
    p.style.width = p.style.height = (2 + Math.random() * 3) + "px";
    voiceParticles.appendChild(p);
  }
  voiceUI.appendChild(voiceParticles);

  // Badge
  const badge = document.createElement("div");
  badge.className = "voice-mode-badge";
  badge.innerText = "VOICE MODE";

  // 👤 User Profile Picture
  const voiceDp = document.createElement("div");
  voiceDp.className = "voice-dp-container";
  const dpImg = document.createElement("img");
  dpImg.className = "voice-dp-img";
  dpImg.id = "voice-dp-img";
  // Try to get profile pic from drawer, fallback to default
  const profileImgEl = document.querySelector(".profile-img");
  dpImg.src = profileImgEl ? profileImgEl.src : "/static/icons/icon-192.png";
  const dpRing = document.createElement("div");
  dpRing.className = "voice-dp-ring";
  voiceDp.append(dpRing, dpImg);

  // Status Text
  const statusText = document.createElement("div");
  statusText.id = "voice-status-text";
  statusText.innerText = "Tap to speak";

  // Mic Button Wrapper (outer ring + inner ring + mic)
  const micWrapper = document.createElement("div");
  micWrapper.className = "mic-btn-wrapper";

  // Outer Conic-Gradient Ring
  const micRing = document.createElement("div");
  micRing.className = "mic-ring-outer";

  // Inner Expanding Ring
  const micRingInner = document.createElement("div");
  micRingInner.className = "mic-ring-inner";

  // Mic Button
  const micBtn = document.createElement("button");
  micBtn.id = "voice-mic-btn";
  micBtn.innerHTML = getIconMarkup("mic");
  micBtn.type = "button";

  micWrapper.append(micRing, micRingInner, micBtn);

  // Make the Speak button wrapper draggable inside the Voice UI
  let micDragStartX = 0, micDragStartY = 0, isMicDragging = false;
  micWrapper.style.cursor = "grab";
  
  Draggable.get(micWrapper)?.kill();
  Draggable.create(micWrapper, {
    type: "x,y",
    bounds: voiceUI,
    inertia: true,
    minimumMovement: 5,
    onDragStart(e) {
      micWrapper.style.cursor = "grabbing";
      const point = e.touches ? e.touches[0] : e;
      micDragStartX = point.clientX;
      micDragStartY = point.clientY;
      isMicDragging = false;
    },
    onDrag(e) {
      const point = e.touches ? e.touches[0] : e;
      const dx = Math.abs(point.clientX - micDragStartX);
      const dy = Math.abs(point.clientY - micDragStartY);
      if (dx > 5 || dy > 5) isMicDragging = true;
    },
    onDragEnd() {
      micWrapper.style.cursor = "grab";
    }
  });

  // Waveform Visualizer
  const waveContainer = document.createElement("div");
  waveContainer.id = "voice-wave";
  for (let i = 0; i < 9; i++) {
    const bar = document.createElement("div");
    bar.className = "wave-bar";
    waveContainer.appendChild(bar);
  }

  // Transcription Preview
  const transcriptionEl = document.createElement("div");
  transcriptionEl.className = "voice-transcription";
  transcriptionEl.id = "voice-transcription";

  // Hint Text
  const hintText = document.createElement("div");
  hintText.className = "voice-hint-text";
  hintText.innerText = "Tap mic to record. Tap again to stop.";

  voiceUI.append(badge, voiceDp, statusText, micWrapper, waveContainer, transcriptionEl, hintText);

  // 🎥 Video Background Element
  const voiceVideo = document.createElement("video");
  voiceVideo.className = "voice-video-bg";
  voiceVideo.id = "voice-video-bg";
  voiceVideo.muted = true;
  voiceVideo.playsInline = true;
  voiceVideo.loop = true;
  voiceVideo.preload = "metadata";
  if (window.__pendingVoiceVideoUrl) {
    voiceVideo.src = window.__pendingVoiceVideoUrl + '?v=' + Date.now();
  }
  voiceUI.insertBefore(voiceVideo, voiceUI.firstChild);

  // Insert voice UI right after the input box (same parent level)
  inputBox.parentElement.insertBefore(voiceUI, inputBox.nextSibling);

  // ==========================================
  // TOGGLE BUTTON (Fixed position)
  // ==========================================
  const existingToggleBtn = document.getElementById("voice-mode-toggle");
  if (existingToggleBtn) {
    Draggable.get(existingToggleBtn)?.kill();
    existingToggleBtn.remove();
  }
  const toggleBtn = document.createElement("button");
  toggleBtn.id = "voice-mode-toggle";
  toggleBtn.type = "button";
  setVoiceToggleContent(toggleBtn, false);
  document.body.appendChild(toggleBtn);

  // Make voice toggle draggable with GSAP (mobile-friendly)
  let savedPos = null;
  try {
    savedPos = JSON.parse(readStorage("voiceBtnPos") || "null");
  } catch {
    removeStorage("voiceBtnPos");
  }
  if (savedPos && Number.isFinite(savedPos.x) && Number.isFinite(savedPos.y)) {
    gsap.set(toggleBtn, { x: savedPos.x, y: savedPos.y });
  }

  // Mobile fix: track drag distance to distinguish taps from drags
  let dragStartX = 0, dragStartY = 0, isDragging = false;
  toggleBtn.style.touchAction = "none"; // Prevent browser scroll interference

  Draggable.get(toggleBtn)?.kill();
  const [toggleDrag] = Draggable.create(toggleBtn, {
    type: "x,y",
    bounds: document.body,
    inertia: true,
    minimumMovement: 2,
    onDragStart(e) {
      const point = e.touches ? e.touches[0] : e;
      dragStartX = point.clientX;
      dragStartY = point.clientY;
      isDragging = false;
    },
    onDrag(e) {
      const point = e.touches ? e.touches[0] : e;
      const dx = Math.abs(point.clientX - dragStartX);
      const dy = Math.abs(point.clientY - dragStartY);
      if (dx > 5 || dy > 5) isDragging = true;
    },
    onDragEnd() {
      clampFloatingButtonPosition(toggleBtn, this);
    }
  });

  const syncFloatingToggleBounds = () => {
    clampFloatingButtonPosition(toggleBtn, toggleDrag);
  };

  requestAnimationFrame(syncFloatingToggleBounds);
  window.addEventListener("resize", syncFloatingToggleBounds);
  window.addEventListener("orientationchange", syncFloatingToggleBounds);
  window.visualViewport?.addEventListener("resize", syncFloatingToggleBounds);

  // Use pointerup instead of click for better mobile support
  toggleBtn.addEventListener("pointerup", (e) => {
    if (isDragging) { isDragging = false; return; }
    e.preventDefault();
    if (inputMode === "chat") {
      activateVoiceMode();
      const modeSelect = document.getElementById("modeSelect");
      if (modeSelect) {
        modeSelect.value = "voice_assistant";
        handleModeChange();
      }
    } else {
      deactivateVoiceMode();
      const modeSelect = document.getElementById("modeSelect");
      if (modeSelect) {
        modeSelect.value = "casual";
        handleModeChange();
      }
    }
  });

  // ==========================================
  // RECORDING LOGIC
  // ==========================================
  micBtn.addEventListener("click", async (e) => {
    e.preventDefault();
    e.stopPropagation();

    if (isRecording) {
      // Stop Recording
      mediaRecorder.stop();
      isRecording = false;
      statusText.innerText = "Processing...";
      waveContainer.classList.remove("active");
      micRing.classList.remove("active");
      micRingInner.classList.remove("active");
      micBtn.classList.remove("recording");
      // Remove recording-wave class from bars
      waveContainer.querySelectorAll(".wave-bar").forEach(b => b.classList.remove("recording-wave"));
      setThinkingState(true);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream);
      audioChunks = [];

      mediaRecorder.ondataavailable = e => {
        if (e.data.size > 0) audioChunks.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
        await processVoiceAPI(audioBlob);
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      isRecording = true;
      statusText.innerText = "Listening...";
      waveContainer.classList.add("active");
      micRing.classList.add("active");
      micRingInner.classList.add("active");
      micBtn.classList.add("recording");
      // Add recording-wave class for red bars
      waveContainer.querySelectorAll(".wave-bar").forEach(b => b.classList.add("recording-wave"));
      transcriptionEl.innerHTML = "";

    } catch (err) {
      console.error("Mic Access Error:", err);
      statusText.innerText = "Mic access denied";
      setTimeout(() => { statusText.innerText = "Tap to speak"; }, 3000);
    }
  });

  // ==========================================
  // SEND TO /voice BACKEND
  // ==========================================
  async function processVoiceAPI(blob) {
    const formData = new FormData();
    formData.append("audio", blob, "voice_record.webm");
    formData.append("mode", "voice_assistant");

    const startTime = performance.now();

    try {
      const res = await fetch("/voice", {
        method: "POST",
        headers: { "X-NEON-KEY": "NEON_LOCAL_SECRET" },
        body: formData
      });

      setThinkingState(false);
      const endTime = performance.now();
      const latency = ((endTime - startTime) / 1000).toFixed(2) + "s";

      const contentType = res.headers.get("content-type") || "";

      if (contentType.includes("audio")) {
        // Got TTS audio back — read the response text from headers
        const responseText = decodeURIComponent(res.headers.get("X-Response-Text") || "");
        const transcription = decodeURIComponent(res.headers.get("X-Transcription") || "");

        const audioBlob = await res.blob();
        const audioUrl = URL.createObjectURL(audioBlob);

        statusText.innerText = "Speaking...";

        // Show what user said in voice UI
        if (transcription) {
          transcriptionEl.innerHTML = `<span class="you-said-label">You said</span>"${transcription}"`;
          addMsg(transcription, "user");
        }

        // Auto-play the response
        const audio = new Audio(audioUrl);
        audio.play().catch(() => { });
        audio.onended = () => {
          statusText.innerText = "Tap to speak";
        };

        // Show Neon's response text in chat with fancy font + audio player
        const displayText = responseText || "Voice response received";
        addMsg(
          `<div class="voice-assistant-msg">${renderMessage(displayText)}</div><audio controls class="voice-audio-player" src="${audioUrl}"></audio>`,
          "assistant",
          null,
          latency
        );

      } else {
        // Got JSON text response (TTS was unavailable)
        const data = await res.json();

        if (data.transcription) {
          // Show stylish transcription in the voice UI
          transcriptionEl.innerHTML = `<span class="you-said-label">You said</span>"${data.transcription}"`;
          // Add user message to chat with handwriting class
          addMsg(data.transcription, "user");
        }

        if (data.error) {
          addMsg("Error: " + data.error, "assistant", null, latency);
        } else if (data.response) {
          addMsg(data.response, "assistant", null, latency);
        }

        statusText.innerText = "Tap to speak";
      }

    } catch (e) {
      setThinkingState(false);
      console.error("Voice Error:", e);
      statusText.innerText = "Connection failed";
      addMsg("Voice connection failed. Check server.", "assistant");
      setTimeout(() => { statusText.innerText = "Tap to speak"; }, 3000);
    }
  }
}

// Add voice user message with stylish handwriting font
function addVoiceUserMsg(text) {
  const chatContainer = document.getElementById("chat-container");
  if (!chatContainer) return;

  // Use mode-specific container
  const container = getOrCreateModeContainer(currentChatMode);
  if (!container) return;
  container.style.display = "block";

  const rowDiv = document.createElement("div");
  rowDiv.className = "chat-row user";

  const storedPic = getUserAvatar();
  const userNameField = document.getElementById("userName");
  const storedName = userNameField ? userNameField.value || "User" : "User";

  rowDiv.innerHTML = `
    <div class="chat-avatar-container">
      <div class="user-avatar-glow"></div>
      <img src="${storedPic}" class="chat-avatar-img chat-user-pic">
    </div>
    <div class="msg-column">
      <div class="chat-name-tag user-name-label">${storedName}</div>
      <div class="msg voice-user-msg">${renderMessage(text)}</div>
    </div>`;

  container.appendChild(rowDiv);
  requestAnimationFrame(() => {
    scheduleChatScroll(chatContainer);
  });
}

// 🎥 Handle Voice Video Upload
function changeVoiceVideo() {
  const fileInput = document.getElementById("voiceVideoUpload");
  if (!fileInput || !fileInput.files[0]) return;

  const file = fileInput.files[0];
  const blobUrl = URL.createObjectURL(file);

  const videoEl = document.getElementById("voice-video-bg");
  if (videoEl) {
    videoEl.src = blobUrl;
    videoEl.load();
    // Display name
    const nameDisplay = document.getElementById("voiceVideoName");
    if (nameDisplay) nameDisplay.innerText = "Saved: " + file.name;

    // If already in voice mode, start playing immediately
    if (inputMode === "voice") {
      syncVoiceVideoPlayback(true);
    }
  }

  // Save to server for persistence across sessions
  const formData = new FormData();
  formData.append("file", file);
  fetch("/upload-voice-video", { method: "POST", body: formData })
    .then(r => r.json())
    .then(data => {
      if (data.status === "success") console.log("[Voice] Video saved to server");
    })
    .catch(() => { });
}

// Auto-play/pause voice video when voice mode toggles
const _origActivate = activateVoiceMode;
activateVoiceMode = function () {
  _origActivate();
  syncVoiceVideoPlayback(true);
};

const _origDeactivate = deactivateVoiceMode;
deactivateVoiceMode = function () {
  _origDeactivate();
  syncVoiceVideoPlayback();
};

function handleBgPresetChange(preset) {
  const bgVideo = document.getElementById('bg-video');
  if (bgVideo) {
    bgVideo.pause();
    bgVideo.removeAttribute('src');
    bgVideo.load();
    bgVideo.classList.remove('playing');
    clearLoopCap(bgVideo);
  }

  if (preset === 'none') {
    document.documentElement.style.setProperty("--bg-image", "none");
    writeStorage("bgMode", "none");
    applyBackgroundModeState("none");
  } else {
    document.documentElement.style.setProperty("--bg-image", "var(--" + preset + ")");
    writeStorage("bgMode", preset);
    applyBackgroundModeState(preset);
  }

  const bgDisplay = document.getElementById("bgNameDisplay");
  if (bgDisplay) bgDisplay.innerText = "Preset Selected";
  syncSoundToggle();
}

/**
 * Persists the floating button position to localStorage
 */
function clampFloatingButtonPosition(btn, draggable) {
  if (!btn || !draggable) return;
  requestAnimationFrame(() => {
    writeStorage("voiceBtnPos", JSON.stringify({ x: draggable.x, y: draggable.y }));
  });
}

/**
 * Defensive cleanup: Ensure the static header mic button is removed if it appears
 */
(function cleanupHeaderVoice() {
  const checkAndRemove = () => {
    const oldBtn = document.getElementById("headerVoiceToggle");
    if (oldBtn) {
      console.log("[Cleanup] Removing legacy headerVoiceToggle");
      oldBtn.remove();
    }
  };
  checkAndRemove();
  // Also check after a short delay for dynamic loads
  setTimeout(checkAndRemove, 500);
  setTimeout(checkAndRemove, 2000);
})();

// ==========================================
// 🧠 LLM PROVIDER & API KEY MANAGEMENT
// ==========================================

const LLM_PROVIDER_HINTS = {
  local: "Using local Ollama models (free)",
  openai: "Using OpenAI ChatGPT (API key required)",
  gemini: "Using Google Gemini (API key required)",
  claude: "Using Anthropic Claude (API key required)",
};

function saveLLMProvider() {
  const select = document.getElementById("llmProviderSelect");
  if (!select) return;

  const provider = select.value;
  const providerName = select.options[select.selectedIndex].text;
  const hint = document.getElementById("llm-provider-hint");

  // Show switching indicator
  if (hint) {
    hint.innerText = `⏳ Switching to ${providerName}... please wait`;
    hint.style.color = "var(--primary-glow, #00ffc8)";
  }
  select.disabled = true;

  console.log(`[LLM] 🔄 Switching provider to: ${providerName} (${provider})`);

  fetch("/set-llm-keys", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ llm_provider: provider }),
  })
    .then((r) => r.json())
    .then((data) => {
      select.disabled = false;
      if (data.status === "success") {
        if (hint) {
          hint.innerText = `✅ ${LLM_PROVIDER_HINTS[provider] || "Provider updated"}`;
          hint.style.color = "";
        }
        addMsg(`LLM Provider switched to: ${providerName}`, "assistant");
        console.log(`[LLM] ✅ Provider switched successfully to: ${providerName}`);
      } else {
        if (hint) {
          hint.innerText = `❌ Failed to switch — ${data.message || "Unknown error"}`;
          hint.style.color = "#ff4444";
        }
        console.error(`[LLM] ❌ Switch failed: ${data.message || "Unknown error"}`);
      }
    })
    .catch((err) => {
      select.disabled = false;
      if (hint) {
        hint.innerText = "❌ Connection error. Try again.";
        hint.style.color = "#ff4444";
      }
      console.error("[LLM] ❌ Switch error:", err);
    });
}

async function saveLLMKeys() {
  const openaiKey = document.getElementById("openaiKeyInput")?.value.trim() || "";
  const geminiKey = document.getElementById("geminiKeyInput")?.value.trim() || "";
  const claudeKey = document.getElementById("claudeKeyInput")?.value.trim() || "";

  if (!openaiKey && !geminiKey && !claudeKey) {
    addMsg("Please enter at least one API key.", "assistant");
    return;
  }

  setThinkingState(true);
  try {
    const payload = {};
    if (openaiKey) payload.openai_key = openaiKey;
    if (geminiKey) payload.gemini_key = geminiKey;
    if (claudeKey) payload.claude_key = claudeKey;

    const res = await fetch("/set-llm-keys", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    setThinkingState(false);

    if (data.status === "success") {
      addMsg("LLM API Keys Saved! You can now select a premium provider above.", "assistant");
    } else {
      addMsg("Error saving keys: " + (data.message || "Unknown error"), "assistant");
    }
  } catch (e) {
    setThinkingState(false);
    addMsg("Failed to save LLM keys. Check server.", "assistant");
  }
}

async function deleteSingleLLMKey(provider) {
  const inputMap = { openai: "openaiKeyInput", gemini: "geminiKeyInput", claude: "claudeKeyInput" };
  const keyField = inputMap[provider];
  const input = keyField ? document.getElementById(keyField) : null;
  if (input) input.value = "";

  const payload = {};
  payload[provider + "_key"] = "";

  try {
    await fetch("/set-llm-keys", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    addMsg(`${provider.charAt(0).toUpperCase() + provider.slice(1)} API key removed.`, "assistant");
  } catch (e) {
    addMsg("Failed to remove key.", "assistant");
  }
}

async function deleteAllLLMKeys() {
  if (!confirm("Remove all LLM API keys?")) return;

  document.getElementById("openaiKeyInput").value = "";
  document.getElementById("geminiKeyInput").value = "";
  document.getElementById("claudeKeyInput").value = "";

  const select = document.getElementById("llmProviderSelect");
  if (select) select.value = "local";

  try {
    await fetch("/set-llm-keys", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        openai_key: "",
        gemini_key: "",
        claude_key: "",
        llm_provider: "local",
      }),
    });
    const hint = document.getElementById("llm-provider-hint");
    if (hint) hint.innerText = LLM_PROVIDER_HINTS.local;
    addMsg("All LLM keys removed. Switched back to Local Ollama.", "assistant");
  } catch (e) {
    addMsg("Failed to clear LLM keys.", "assistant");
  }
}

// Restore LLM settings from server on page load
function restoreLLMSettings(data) {
  const select = document.getElementById("llmProviderSelect");
  if (select && data.llm_provider) {
    select.value = data.llm_provider;
    const hint = document.getElementById("llm-provider-hint");
    if (hint) hint.innerText = LLM_PROVIDER_HINTS[data.llm_provider] || "";
  }

  // Show placeholder text if key exists on server
  if (data.has_openai_key) {
    const el = document.getElementById("openaiKeyInput");
    if (el) el.placeholder = "OpenAI Key (saved ✓)";
  }
  if (data.has_gemini_key) {
    const el = document.getElementById("geminiKeyInput");
    if (el) el.placeholder = "Gemini Key (saved ✓)";
  }
  if (data.has_claude_key) {
    const el = document.getElementById("claudeKeyInput");
    if (el) el.placeholder = "Claude Key (saved ✓)";
  }
}

// ==========================================
// 📷 VISION / RESUME ANALYZER
// ==========================================

async function analyzeVisionImage() {
  const fileInput = document.getElementById("visionUpload");
  if (!fileInput || !fileInput.files[0]) return;

  const file = fileInput.files[0];
  const nameDisplay = document.getElementById("visionFileName");
  if (nameDisplay) nameDisplay.innerText = file.name;

  const isPDF = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");

  if (!isPDF) {
    alert("Please upload a PDF file for Resume Analysis.");
    return;
  }

  const queryInput = document.getElementById("visionQuery");
  let query = queryInput ? queryInput.value.trim() : "";

  // Auto-set resume query for PDFs if user didn't type anything
  if (!query) {
    query = "Analyze this resume and give ATS score with suggestions";
  }

  const resultDiv = document.getElementById("visionResult");
  if (resultDiv) {
    resultDiv.style.display = "block";
    resultDiv.innerHTML = "⏳ Analyzing resume PDF... Extracting text & generating ATS score...";
  }

  // Read file as base64
  const reader = new FileReader();
  reader.onload = async function (e) {
    const base64Data = e.target.result;

    try {
      const res = await fetch("/api/analyze-image", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image: base64Data,
          query: query,
          file_type: "pdf",
        }),
      });

      const data = await res.json();

      if (resultDiv) {
        if (data.status === "success") {
          resultDiv.innerHTML = `<strong>🤖 ${data.model || "AI"}:</strong>\n\n${data.response}`;
        } else {
          resultDiv.innerHTML = `⚠️ ${data.response || data.message || "Analysis failed."}`;
        }
      }

      // Also add to chat
      if (data.status === "success") {
        addMsg(
          `📄 Resume ATS Analysis (${data.model || "AI"}):\n\n${data.response}`,
          "assistant"
        );
      }
    } catch (err) {
      if (resultDiv) resultDiv.innerHTML = "❌ Failed to connect to server. Is Ollama running?";
    }
  };

  reader.readAsDataURL(file);
}

// ==========================================
// 📷 INLINE CHAT IMAGE UPLOAD
// ==========================================

let pendingChatImage = null;

async function handleChatImageUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  if (!file.type.startsWith("image/")) {
    addMsg("⚠️ Please upload a valid image file (PNG, JPG, WEBP, etc.).", "assistant");
    event.target.value = "";
    return;
  }

  // Validate file size (max 10MB)
  const MAX_SIZE_MB = 10;
  if (file.size > MAX_SIZE_MB * 1024 * 1024) {
    addMsg(`⚠️ Image is too large (${(file.size / 1024 / 1024).toFixed(1)}MB). Max size is ${MAX_SIZE_MB}MB.`, "assistant");
    event.target.value = "";
    return;
  }

  // Create a blob URL to show a temporary preview in the chat input
  const blobUrl = URL.createObjectURL(file);
  pendingChatImage = file;

  // Show pinned preview above the chat bar
  const previewContainer = document.getElementById("chat-image-preview-container");
  const previewImg = document.getElementById("chat-image-preview");
  
  if (previewContainer && previewImg) {
    previewImg.src = blobUrl;
    previewContainer.style.display = "flex";
  }
  
  // Set focus to the input box so the user can type their prompt
  const userInput = document.getElementById("userInput");
  if (userInput) {
    userInput.focus();
    userInput.placeholder = "Ask about this image... (or just send)";
  }

  console.log(`[Chat Image] 📸 Attached: "${file.name}" | Size: ${(file.size / 1024).toFixed(1)}KB | Type: ${file.type}`);
}

function clearChatImage() {
  pendingChatImage = null;
  const previewContainer = document.getElementById("chat-image-preview-container");
  const previewImg = document.getElementById("chat-image-preview");
  const fileInput = document.getElementById("chatImageUpload");
  
  if (previewContainer && previewImg) {
    previewContainer.style.display = "none";
    previewImg.src = "";
  }
  if (fileInput) fileInput.value = "";
  
  const userInput = document.getElementById("userInput");
  if (userInput) {
    userInput.placeholder = "Type command...";
    userInput.focus();
  }
}

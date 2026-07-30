/* 지원사업 알리미 — client-side matching & rendering */
(function () {
  "use strict";

  const STORAGE_KEY = "gov-profile";
  const SOURCE_LABELS = {
    kstartup: "K-Startup",
    bizinfo: "기업마당",
    mss: "중기부",
    kised: "창업진흥원",
    kotra: "KOTRA",
    sbiz24: "판판대로",
  };

  const PROFILE_FIELDS = [
    "bizType",
    "bizRegion",
    "bizRevenue",
    "bizAge",
    "bizEmployees",
  ];

  let allItems = [];
  let activeSource = "all";
  let profile = null;

  /* ── Profile ─────────────────────────────────── */

  function loadProfile() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }

  function saveProfile() {
    const p = {};
    PROFILE_FIELDS.forEach((id) => {
      p[id] = document.getElementById(id).value;
    });
    localStorage.setItem(STORAGE_KEY, JSON.stringify(p));
    profile = p;
    render();
  }

  function resetProfile() {
    localStorage.removeItem(STORAGE_KEY);
    PROFILE_FIELDS.forEach((id) => {
      document.getElementById(id).selectedIndex = 0;
    });
    profile = null;
    render();
  }

  function restoreProfile() {
    profile = loadProfile();
    if (!profile) return;
    PROFILE_FIELDS.forEach((id) => {
      const el = document.getElementById(id);
      if (el && profile[id]) el.value = profile[id];
    });
  }

  /* ── Matching ────────────────────────────────── */

  function matchItem(item) {
    if (!profile) return { level: "none", score: 0 };

    const text = [
      item.title || "",
      item.program || "",
      item.category || "",
      item.org || "",
    ]
      .join(" ")
      .toLowerCase();

    let hits = 0;
    let checks = 0;

    if (profile.bizType) {
      checks++;
      const typeMap = {
        제조: ["제조", "생산", "공장", "산업"],
        서비스: ["서비스", "용역"],
        IT: ["it", "sw", "소프트웨어", "디지털", "ai", "ict", "테크", "정보"],
        유통: ["유통", "판매", "쇼핑", "상점", "소매", "도매"],
        요식: ["요식", "외식", "음식", "식품", "카페", "식당"],
        뷰티: ["뷰티", "패션", "화장", "미용", "향수", "의류"],
        교육: ["교육", "학원", "에듀"],
      };
      const keywords = typeMap[profile.bizType] || [];
      if (keywords.some((kw) => text.includes(kw))) hits++;
    }

    if (profile.bizAge) {
      checks++;
      const ageMap = {
        pre: ["예비", "예비창업", "창업준비"],
        u1: ["1년", "초기", "신설"],
        u3: ["3년", "초기", "성장초기"],
        u7: ["7년", "성장", "도약"],
        o7: ["재창업", "혁신"],
      };
      const keywords = ageMap[profile.bizAge] || [];
      if (keywords.some((kw) => text.includes(kw))) hits++;
    }

    if (profile.bizRevenue) {
      checks++;
      const revMap = {
        pre: ["예비", "매출전"],
        u1: ["소상공인", "소기업", "영세"],
        u5: ["소기업", "소상공인", "중소"],
        u10: ["중소", "중기업"],
        o10: ["중견", "강소"],
      };
      const keywords = revMap[profile.bizRevenue] || [];
      if (keywords.some((kw) => text.includes(kw))) hits++;
    }

    if (profile.bizEmployees) {
      checks++;
      const empMap = {
        1: ["1인", "소상공인", "1인창조"],
        u5: ["소상공인", "소기업"],
        u10: ["소기업", "중소"],
        o10: ["중소기업", "중기업"],
      };
      const keywords = empMap[profile.bizEmployees] || [];
      if (keywords.some((kw) => text.includes(kw))) hits++;
    }

    if (checks === 0) return { level: "none", score: 0 };

    const ratio = hits / checks;
    if (ratio >= 0.5) return { level: "fit", score: ratio };
    if (hits > 0) return { level: "maybe", score: ratio };
    return { level: "low", score: 0 };
  }

  /* ── D-day ───────────────────────────────────── */

  function calcDday(deadline) {
    if (!deadline) return null;
    try {
      const d = new Date(deadline + "T23:59:59");
      const now = new Date();
      const diff = Math.ceil((d - now) / (1000 * 60 * 60 * 24));
      return diff;
    } catch {
      return null;
    }
  }

  function ddayText(days) {
    if (days === null) return "";
    if (days < 0) return "마감";
    if (days === 0) return "D-Day";
    return `D-${days}`;
  }

  function ddayClass(days) {
    if (days === null) return "";
    if (days <= 3) return "dday-urgent";
    if (days <= 14) return "dday-soon";
    return "dday-ok";
  }

  /* ── Render ──────────────────────────────────── */

  function getSearchQuery() {
    return (document.getElementById("searchInput").value || "")
      .trim()
      .toLowerCase();
  }

  function filterItems() {
    const q = getSearchQuery();
    return allItems.filter((item) => {
      if (activeSource !== "all" && item.source !== activeSource) return false;
      if (q) {
        const text = [item.title || "", item.org || "", item.program || ""]
          .join(" ")
          .toLowerCase();
        if (!text.includes(q)) return false;
      }
      return true;
    });
  }

  function renderCard(item) {
    const match = matchItem(item);
    const days = calcDday(item.deadline);
    const dday = ddayText(days);

    let badgeHtml = "";
    if (match.level === "fit") {
      badgeHtml = '<span class="badge badge-fit">적합</span>';
    } else if (match.level === "maybe") {
      badgeHtml = '<span class="badge badge-maybe">관련</span>';
    }

    const sourceName = SOURCE_LABELS[item.source] || item.source;
    const deadlineStr = item.deadline || "";
    const orgStr = item.org || "";
    const catStr = item.category || "";

    const metaParts = [];
    metaParts.push(`<span class="badge badge-source">${sourceName}</span>`);
    if (orgStr)
      metaParts.push(`<span>${orgStr}</span>`);
    if (deadlineStr) {
      const cls = ddayClass(days);
      metaParts.push(
        `<span>마감 ${deadlineStr} <strong class="dday ${cls}">${dday}</strong></span>`
      );
    }

    const tags = [];
    if (catStr) tags.push(catStr);
    if (item.program) tags.push(item.program);
    const tagsHtml = tags.length
      ? `<div class="grant-tags">${tags.map((t) => `<span class="tag">${t}</span>`).join("")}</div>`
      : "";

    return `<article class="grant-card" data-match="${match.level}">
  <div class="grant-top">
    <div class="grant-title"><a href="${item.url}" target="_blank" rel="noopener">${item.title}</a></div>
    ${badgeHtml}
  </div>
  <div class="grant-meta">${metaParts.join("")}</div>
  ${tagsHtml}
</article>`;
  }

  function render() {
    const list = document.getElementById("grantsList");
    const stats = document.getElementById("stats");
    const items = filterItems();

    if (profile) {
      items.forEach((it) => {
        it._match = matchItem(it);
      });
      items.sort((a, b) => {
        const levelOrder = { fit: 0, maybe: 1, low: 2, none: 2 };
        const la = levelOrder[a._match.level] ?? 2;
        const lb = levelOrder[b._match.level] ?? 2;
        if (la !== lb) return la - lb;
        return b._match.score - a._match.score;
      });
    }

    const fitCount = items.filter(
      (it) => it._match && it._match.level === "fit"
    ).length;
    const maybeCount = items.filter(
      (it) => it._match && it._match.level === "maybe"
    ).length;

    let statsText = `${items.length}건`;
    if (profile && (fitCount || maybeCount)) {
      statsText += ` (적합 ${fitCount} · 관련 ${maybeCount})`;
    }
    stats.textContent = statsText;

    if (items.length === 0) {
      list.innerHTML =
        '<div class="empty-state"><p>조건에 맞는 공고가 없습니다.</p></div>';
      return;
    }

    list.innerHTML = items.map(renderCard).join("");
  }

  /* ── Init ────────────────────────────────────── */

  function initChips() {
    document.querySelectorAll(".chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        document
          .querySelectorAll(".chip")
          .forEach((c) => c.classList.remove("active"));
        chip.classList.add("active");
        activeSource = chip.dataset.source;
        render();
      });
    });
  }

  async function loadData() {
    try {
      const resp = await fetch("data.json");
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      allItems = data.items || [];
      document.getElementById("updated").textContent = data.updated || "-";
      render();
    } catch (err) {
      document.getElementById("grantsList").innerHTML =
        '<div class="empty-state"><p>데이터를 불러올 수 없습니다. 잠시 후 다시 시도해주세요.</p></div>';
      console.error("data load failed:", err);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    restoreProfile();
    initChips();

    document.getElementById("saveProfile").addEventListener("click", saveProfile);
    document.getElementById("resetProfile").addEventListener("click", resetProfile);
    document.getElementById("searchInput").addEventListener("input", render);

    loadData();
  });
})();

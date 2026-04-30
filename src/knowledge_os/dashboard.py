#!/usr/bin/env python3
"""
knowledge-os local dashboard
Run with: venv/bin/python -m streamlit run src/knowledge_os/dashboard.py
"""
import json
import sqlite3
import sys
import urllib.request
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

DB_PATH = "hn_digest_v2.db"
CONFIG_PATH = "config.json"

st.set_page_config(layout="wide", page_title="knowledge-os", page_icon="🦅")


# ── Helpers ─────────────────────────────────────────────────────────────────

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


@st.cache_resource(show_spinner="Loading embedding model…")
def get_topic_matcher():
    try:
        from .match_topics import TopicMatcher
    except ImportError:
        from knowledge_os.match_topics import TopicMatcher
    return TopicMatcher(config_path=CONFIG_PATH)


def query(sql, params=()):
    conn = get_conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def scalar(sql, params=()):
    conn = get_conn()
    try:
        row = conn.execute(sql, params).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


# ── Mode switcher ─────────────────────────────────────────────────────────────

st.sidebar.title("🦅 knowledge-os")
mode = st.sidebar.radio("View", ["PM", "Engineering"], label_visibility="collapsed",
                         format_func=lambda x: f"{'📊' if x == 'PM' else '⚙️'}  {x}")
st.sidebar.divider()


# ══════════════════════════════════════════════════════════════════════════════
# PM MODE
# ══════════════════════════════════════════════════════════════════════════════

if mode == "PM":
    st.title("📊 PM View")
    tabs = st.tabs(["Overview", "Browse", "Authors"])


    # ── PM Tab 1: Overview ────────────────────────────────────────────────────

    with tabs[0]:
        st.header("Overview")

        # ── Core metrics ──
        total_items = scalar("SELECT COUNT(*) FROM items") or 0
        hn_items = scalar("SELECT COUNT(*) FROM items WHERE source = 'hackernews'") or 0
        sub_items = scalar("SELECT COUNT(*) FROM items WHERE source = 'substack'") or 0
        total_digests = scalar("SELECT COUNT(*) FROM digests") or 0
        last_digest = scalar("SELECT MAX(sent_at) FROM digests")
        notable_authors = scalar("SELECT COUNT(*) FROM authors WHERE story_count >= 3") or 0

        try:
            eng_detected = scalar("SELECT COALESCE(SUM(1),0) FROM engagement_opportunities") or 0
            eng_engaged = scalar(
                "SELECT COALESCE(SUM(CASE WHEN engaged=1 THEN 1 ELSE 0 END),0) "
                "FROM engagement_opportunities"
            ) or 0
        except Exception:
            eng_detected = eng_engaged = 0

        avg_per_digest = round(total_items / total_digests, 1) if total_digests else 0
        eng_rate = round(eng_engaged / eng_detected * 100) if eng_detected else 0

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Digests sent", total_digests)
        c2.metric("Avg stories / digest", avg_per_digest)
        c3.metric("Engagement opps", eng_detected)
        c4.metric("Acted on", f"{eng_engaged} ({eng_rate}%)")
        c5.metric("Notable authors", notable_authors)

        if last_digest:
            st.caption(f"Last digest: {last_digest[:19]}")

        st.divider()

        # ── Match quality ──
        st.subheader("Match quality")

        avg_score = scalar("""
            SELECT AVG(score) FROM item_topic_scores
            WHERE score = (
                SELECT MAX(s2.score) FROM item_topic_scores s2
                WHERE s2.item_id = item_topic_scores.item_id
            )
        """)
        cfg_now = load_config()
        threshold = cfg_now["settings"].get("similarity_threshold", 0.3)

        mq1, mq2, mq3 = st.columns(3)
        mq1.metric("Avg best-match score", f"{avg_score:.3f}" if avg_score else "—")
        mq2.metric("Similarity threshold", threshold)
        if avg_score:
            headroom = round((avg_score - threshold) / threshold * 100)
            mq3.metric("Headroom above threshold", f"{headroom}%",
                       delta="comfortable" if headroom > 30 else "tight")

        # Score distribution bucketed into 0.1-width bins
        score_rows = query("""
            SELECT score FROM item_topic_scores
            WHERE score = (
                SELECT MAX(s2.score) FROM item_topic_scores s2
                WHERE s2.item_id = item_topic_scores.item_id
            )
        """)
        if score_rows:
            import math
            buckets = {}
            for r in score_rows:
                s = r["score"]
                bucket = f"{math.floor(s * 10) / 10:.1f}–{math.floor(s * 10) / 10 + 0.1:.1f}"
                buckets[bucket] = buckets.get(bucket, 0) + 1
            st.bar_chart(pd.DataFrame.from_dict(buckets, orient="index", columns=["count"])
                         .sort_index())
            st.caption("Distribution of top topic scores across all stored items")

        st.divider()

        # ── Topic coverage ──
        st.subheader("Content by topic")

        topic_counts = query("""
            SELECT t.name AS topic, COUNT(its.item_id) AS count
            FROM item_topic_scores its
            JOIN topics t ON its.topic_id = t.topic_id
            WHERE its.score = (
                SELECT MAX(its2.score)
                FROM item_topic_scores its2
                WHERE its2.item_id = its.item_id
            )
            GROUP BY t.name
            ORDER BY count DESC
        """)
        if topic_counts:
            df_topics = pd.DataFrame(topic_counts).set_index("topic")
            st.bar_chart(df_topics["count"])

        st.divider()

        # ── Recent digest history ──
        st.subheader("Recent digests")
        digests = query("""
            SELECT digest_id, sent_at,
                   LENGTH(item_ids) - LENGTH(REPLACE(item_ids, ',', '')) + 1 AS item_count
            FROM digests ORDER BY sent_at DESC LIMIT 10
        """)
        if digests:
            st.dataframe(pd.DataFrame(digests), use_container_width=True, hide_index=True)


    # ── PM Tab 2: Browse ──────────────────────────────────────────────────────

    with tabs[1]:
        st.header("Browse")

        cfg_browse = load_config()
        topic_names = [t["name"] for t in cfg_browse["topics"]]

        b1, b2, b3 = st.columns([2, 1, 1])
        browse_topic = b1.selectbox("Topic", ["All"] + topic_names, key="browse_topic")
        browse_days = b2.number_input("Days back", min_value=1, max_value=90, value=15, key="browse_days")
        browse_source = b3.selectbox("Source", ["All", "hackernews", "substack"], key="browse_source")

        cutoff_browse = (datetime.now() - timedelta(days=int(browse_days))).isoformat()

        if browse_topic == "All":
            browse_sql = """
                SELECT DISTINCT i.item_id, i.title, i.url, i.source, i.author,
                       i.score, i.published_at,
                       (
                           SELECT t.name FROM item_topic_scores its2
                           JOIN topics t ON its2.topic_id = t.topic_id
                           WHERE its2.item_id = i.item_id
                           ORDER BY its2.score DESC LIMIT 1
                       ) AS top_topic,
                       (
                           SELECT MAX(its3.score) FROM item_topic_scores its3
                           WHERE its3.item_id = i.item_id
                       ) AS top_score
                FROM items i
                WHERE i.published_at != ''
                  AND i.published_at >= ?
                {source_clause}
                ORDER BY i.published_at DESC
                LIMIT 200
            """
        else:
            browse_sql = """
                SELECT i.item_id, i.title, i.url, i.source, i.author,
                       i.score, i.published_at,
                       t.name AS top_topic,
                       its.score AS top_score
                FROM items i
                JOIN item_topic_scores its ON i.item_id = its.item_id
                JOIN topics t ON its.topic_id = t.topic_id
                WHERE t.name = ?
                  AND i.published_at != ''
                  AND i.published_at >= ?
                {source_clause}
                ORDER BY i.published_at DESC
                LIMIT 200
            """

        source_clause = "AND i.source = ?" if browse_source != "All" else ""
        browse_sql = browse_sql.format(source_clause=source_clause)

        if browse_topic == "All":
            browse_params = [cutoff_browse]
        else:
            browse_params = [browse_topic, cutoff_browse]

        if browse_source != "All":
            browse_params.append(browse_source)

        browse_rows = query(browse_sql, browse_params)

        st.caption(f"{len(browse_rows)} stories")

        if not browse_rows:
            st.info("No stories found for this selection. Try a wider date range or different topic.")
        else:
            by_date = {}
            for row in browse_rows:
                day = row["published_at"][:10]
                by_date.setdefault(day, []).append(row)

            for day, day_rows in by_date.items():
                st.markdown(f"### {day}")
                for row in day_rows:
                    source = row["source"]
                    source_badge = "📰 Substack" if source == "substack" else "🔶 HN"
                    score_str = f"↑{row['score']}" if row["score"] else ""
                    topic_str = f"· {row['top_topic']}" if row.get("top_topic") else ""
                    topic_sim = f"({row['top_score']:.2f})" if row.get("top_score") else ""

                    with st.container(border=True):
                        title_col, meta_col = st.columns([5, 1])
                        with title_col:
                            st.markdown(f"**[{row['title']}]({row['url']})**")
                            st.caption(
                                f"{source_badge} · {row['author']} {score_str} {topic_str} {topic_sim}"
                            )
                        with meta_col:
                            st.link_button("Open →", row["url"])
                st.divider()


    # ── PM Tab 3: Authors ─────────────────────────────────────────────────────

    with tabs[2]:
        st.header("Authors")
        st.caption("Who keeps showing up — sorted by signal, not just volume.")

        a1, a2 = st.columns(2)
        min_stories = a1.number_input("Min story count", min_value=1, value=2)
        sort_by = a2.selectbox("Sort by", ["story_count", "total_score", "last_seen"])

        authors = query(f"""
            SELECT author_name, story_count, total_score, topics, last_seen, first_seen
            FROM authors
            WHERE story_count >= ?
            ORDER BY {sort_by} DESC
            LIMIT 200
        """, [min_stories])

        if authors:
            rows_display = []
            for a in authors:
                topic_dict = json.loads(a["topics"]) if a["topics"] else {}
                top_topics = sorted(topic_dict.items(), key=lambda x: x[1], reverse=True)[:3]
                tags = " · ".join(f"{k} ({v:.2f})" for k, v in top_topics)
                rows_display.append({
                    "author": a["author_name"],
                    "stories": a["story_count"],
                    "avg score": round(float(a["total_score"]) / a["story_count"], 1) if a["story_count"] else 0,
                    "top topics": tags,
                    "last seen": (a["last_seen"] or "")[:10],
                })
            st.dataframe(pd.DataFrame(rows_display), use_container_width=True, hide_index=True)
            st.caption(f"{len(authors)} authors")
        else:
            st.info("No authors found yet.")


# ══════════════════════════════════════════════════════════════════════════════
# ENGINEERING MODE
# ══════════════════════════════════════════════════════════════════════════════

else:
    st.title("⚙️ Engineering View")
    tabs = st.tabs(["Pipeline", "Stories", "Config", "Simulator"])


    # ── Engg Tab 1: Pipeline Health ───────────────────────────────────────────

    with tabs[0]:
        st.header("Pipeline Health")

        # DB table row counts
        st.subheader("Database")
        db_stats = {}
        for table in ["items", "topics", "item_topic_scores", "authors", "digests"]:
            db_stats[table] = scalar(f"SELECT COUNT(*) FROM {table}") or 0
        try:
            db_stats["engagement_opportunities"] = (
                scalar("SELECT COUNT(*) FROM engagement_opportunities") or 0
            )
        except Exception:
            pass

        cols = st.columns(len(db_stats))
        for col, (table, count) in zip(cols, db_stats.items()):
            col.metric(table, count)

        st.divider()

        # Stories ingested per day by source
        st.subheader("Ingest volume (last 30 days)")
        cutoff_30 = (datetime.now() - timedelta(days=30)).isoformat()
        daily_ingest = query("""
            SELECT substr(fetched_at, 1, 10) AS day, source, COUNT(*) AS count
            FROM items
            WHERE fetched_at >= ?
            GROUP BY day, source
            ORDER BY day
        """, [cutoff_30])

        if daily_ingest:
            df_ingest = pd.DataFrame(daily_ingest)
            df_pivot = df_ingest.pivot(index="day", columns="source", values="count").fillna(0)
            st.bar_chart(df_pivot)
        else:
            st.info("No ingest data for the last 30 days.")

        st.divider()

        # Score distribution
        st.subheader("Topic score distribution (all time)")
        score_dist = query("""
            SELECT score FROM item_topic_scores
            WHERE score = (
                SELECT MAX(s2.score) FROM item_topic_scores s2
                WHERE s2.item_id = item_topic_scores.item_id
            )
        """)
        if score_dist:
            import math
            buckets = {}
            for r in score_dist:
                s = r["score"]
                b = round(math.floor(s * 10) / 10, 1)
                label = f"{b:.1f}"
                buckets[label] = buckets.get(label, 0) + 1
            cfg_now = load_config()
            thresh = cfg_now["settings"].get("similarity_threshold", 0.3)
            st.bar_chart(
                pd.DataFrame.from_dict(buckets, orient="index", columns=["count"]).sort_index()
            )
            st.caption(f"Similarity threshold is {thresh}. Items left of that line are filtered out.")

        st.divider()

        # HN score distribution
        st.subheader("HN upvote score distribution (last 30 days)")
        hn_scores = query("""
            SELECT score FROM items
            WHERE source = 'hackernews'
              AND fetched_at >= ?
              AND score IS NOT NULL
        """, [cutoff_30])
        if hn_scores:
            import math
            buckets_hn = {}
            for r in hn_scores:
                s = int(r["score"] or 0)
                b = (s // 50) * 50
                label = f"{b}–{b+49}"
                buckets_hn[label] = buckets_hn.get(label, 0) + 1
            st.bar_chart(
                pd.DataFrame.from_dict(buckets_hn, orient="index", columns=["count"]).sort_index()
            )


    # ── Engg Tab 2: Stories ───────────────────────────────────────────────────

    with tabs[1]:
        st.header("Stories")

        f1, f2, f3, f4, f5 = st.columns([1, 1, 1, 1, 2])
        source_filter = f1.selectbox("Source", ["All", "hackernews", "substack"])
        min_score_filter = f2.number_input("Min score", min_value=0, value=0, step=10)
        days_back = f3.number_input("Days back", min_value=1, max_value=365, value=30)
        topic_options = ["All"] + [t["name"] for t in load_config()["topics"]]
        topic_filter = f4.selectbox("Topic", topic_options)
        author_filter = f5.text_input("Author contains")

        cutoff = (datetime.now() - timedelta(days=int(days_back))).isoformat()

        base_sql = """
            SELECT i.item_id, i.title, i.source, i.author, i.score,
                   i.fetched_at, i.url
            FROM items i
            WHERE i.fetched_at >= ?
              AND i.score >= ?
        """
        params = [cutoff, min_score_filter]

        if source_filter != "All":
            base_sql += " AND i.source = ?"
            params.append(source_filter)

        if author_filter.strip():
            base_sql += " AND i.author LIKE ?"
            params.append(f"%{author_filter.strip()}%")

        if topic_filter != "All":
            base_sql += """
                AND i.item_id IN (
                    SELECT its.item_id FROM item_topic_scores its
                    JOIN topics t ON its.topic_id = t.topic_id
                    WHERE t.name = ?
                    AND its.score = (
                        SELECT MAX(its2.score) FROM item_topic_scores its2
                        WHERE its2.item_id = its.item_id
                    )
                )
            """
            params.append(topic_filter)

        base_sql += " ORDER BY i.fetched_at DESC LIMIT 500"

        rows = query(base_sql, params)
        st.caption(f"{len(rows)} items")

        if rows:
            df = pd.DataFrame(rows)
            df["fetched_at"] = df["fetched_at"].str[:19]

            page_size = 25
            total_pages = max(1, (len(df) - 1) // page_size + 1)
            page = st.number_input("Page", min_value=1, max_value=total_pages, value=1) - 1
            page_df = df.iloc[page * page_size:(page + 1) * page_size]

            selected = st.dataframe(
                page_df[["item_id", "title", "source", "author", "score", "fetched_at"]],
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
            )

            sel_rows = selected.selection.rows if hasattr(selected, "selection") else []
            if sel_rows:
                sel_item_id = page_df.iloc[sel_rows[0]]["item_id"]
                st.markdown(f"**URL:** {page_df.iloc[sel_rows[0]]['url']}")
                topic_scores = query("""
                    SELECT t.name, its.score
                    FROM item_topic_scores its
                    JOIN topics t ON its.topic_id = t.topic_id
                    WHERE its.item_id = ?
                    ORDER BY its.score DESC
                """, [sel_item_id])
                if topic_scores:
                    st.markdown("**Topic scores:**")
                    ts_df = pd.DataFrame(topic_scores)
                    st.bar_chart(ts_df.set_index("name")["score"])


    # ── Engg Tab 3: Config ────────────────────────────────────────────────────

    with tabs[2]:
        st.header("Config")
        cfg = load_config()

        with st.expander("Topics", expanded=True):
            with st.form("topics_form"):
                updated_topics = []
                for i, topic in enumerate(cfg["topics"]):
                    st.markdown(f"**{topic['name']}**")
                    c1, c2 = st.columns([3, 1])
                    kw_raw = c1.text_input(
                        "Keywords (comma-separated)",
                        value=", ".join(topic["keywords"]),
                        key=f"kw_{i}",
                    )
                    weight = c2.slider(
                        "Weight",
                        min_value=0.1,
                        max_value=2.0,
                        value=float(topic.get("weight", 1.0)),
                        step=0.1,
                        key=f"w_{i}",
                    )
                    updated_topics.append({
                        "name": topic["name"],
                        "keywords": [k.strip() for k in kw_raw.split(",") if k.strip()],
                        "weight": weight,
                    })
                    st.markdown("---")

                new_topic_name = st.text_input("Add new topic name")
                new_topic_kw = st.text_input("Keywords for new topic (comma-separated)")

                if st.form_submit_button("Save topics"):
                    if new_topic_name.strip():
                        updated_topics.append({
                            "name": new_topic_name.strip(),
                            "keywords": [k.strip() for k in new_topic_kw.split(",") if k.strip()],
                            "weight": 1.0,
                        })
                    cfg["topics"] = updated_topics
                    save_config(cfg)
                    st.success("Topics saved.")
                    st.cache_resource.clear()

            topic_names_cfg = [t["name"] for t in cfg["topics"]]
            remove_name = st.selectbox("Remove topic", ["— select —"] + topic_names_cfg)
            if st.button("Remove selected topic") and remove_name != "— select —":
                cfg["topics"] = [t for t in cfg["topics"] if t["name"] != remove_name]
                save_config(cfg)
                st.success(f"Removed {remove_name}.")
                st.rerun()

        with st.expander("Sources"):
            with st.form("sources_form"):
                _freq_opts = ["daily", "weekly", "biweekly", "monthly", "quarterly"]

                st.markdown("**Hacker News**")
                hn_cfg = cfg["sources"]["hackernews"]
                hn_enabled = st.checkbox("Enabled", value=hn_cfg.get("enabled", True), key="hn_enabled")
                _hn_freq_val = hn_cfg.get("frequency", "daily")
                hn_freq = st.selectbox(
                    "Frequency",
                    _freq_opts,
                    index=_freq_opts.index(_hn_freq_val) if _hn_freq_val in _freq_opts else 0,
                    key="hn_freq",
                )

                st.markdown("**Substack**")
                sub_cfg = cfg["sources"]["substack"]
                sub_enabled = st.checkbox("Enabled", value=sub_cfg.get("enabled", True), key="sub_enabled")
                _sub_freq_val = sub_cfg.get("frequency", "daily")
                sub_freq = st.selectbox(
                    "Default frequency",
                    _freq_opts,
                    index=_freq_opts.index(_sub_freq_val) if _sub_freq_val in _freq_opts else 0,
                    key="sub_freq",
                    help="Default for feeds without a per-feed override.",
                )

                # Normalize feeds: extract URLs for display, preserve dict entries on save
                raw_feeds = sub_cfg.get("feeds", [])
                _feed_map = {
                    (f["url"] if isinstance(f, dict) else f): f
                    for f in raw_feeds
                }
                feeds_text = st.text_area(
                    "Substack feeds (one URL per line)",
                    value="\n".join(_feed_map.keys()),
                    height=120,
                    help="Per-feed frequency overrides (set via config as dicts) are preserved when you save.",
                )
                _overrides = [u for u, f in _feed_map.items() if isinstance(f, dict)]
                if _overrides:
                    st.caption(f"{len(_overrides)} feed(s) have per-feed frequency overrides — preserved on save.")

                sub_max = st.number_input(
                    "Max Substack items per feed",
                    min_value=1,
                    max_value=50,
                    value=int(sub_cfg.get("max_items", 10)),
                )

                if st.form_submit_button("Save sources"):
                    new_urls = [u.strip() for u in feeds_text.splitlines() if u.strip()]
                    # Preserve dict entries for known URLs; new URLs saved as plain strings
                    new_feeds = [
                        _feed_map[u] if u in _feed_map and isinstance(_feed_map[u], dict) else u
                        for u in new_urls
                    ]
                    cfg["sources"]["hackernews"]["enabled"] = hn_enabled
                    cfg["sources"]["hackernews"]["frequency"] = hn_freq
                    cfg["sources"]["substack"]["enabled"] = sub_enabled
                    cfg["sources"]["substack"]["frequency"] = sub_freq
                    cfg["sources"]["substack"]["feeds"] = new_feeds
                    cfg["sources"]["substack"]["max_items"] = int(sub_max)
                    save_config(cfg)
                    st.success("Sources saved.")

        with st.expander("Settings"):
            with st.form("settings_form"):
                s = cfg["settings"]
                col1, col2 = st.columns(2)
                with col1:
                    max_stories = st.slider("max_stories", 5, 100, int(s.get("max_stories", 30)))
                    min_score = st.slider("min_score (HN upvotes)", 0, 500, int(s.get("min_score", 50)))
                    max_age = st.slider("max_age_days", 1, 30, int(s.get("max_age_days", 7)),
                                        help="Stories older than this are dropped before topic matching.")
                with col2:
                    sim_thresh = st.slider(
                        "similarity_threshold",
                        0.0, 1.0, float(s.get("similarity_threshold", 0.3)), step=0.01,
                    )
                    notable_thresh = st.number_input(
                        "notable_author_threshold",
                        min_value=1,
                        max_value=20,
                        value=int(s.get("notable_author_threshold", 3)),
                    )
                    digest_time = st.text_input("digest_time (HH:MM)", value=s.get("digest_time", "14:00"))
                if st.form_submit_button("Save settings"):
                    cfg["settings"]["max_stories"] = max_stories
                    cfg["settings"]["min_score"] = min_score
                    cfg["settings"]["max_age_days"] = max_age
                    cfg["settings"]["similarity_threshold"] = sim_thresh
                    cfg["settings"]["notable_author_threshold"] = int(notable_thresh)
                    cfg["settings"]["digest_time"] = digest_time
                    save_config(cfg)
                    st.success("Settings saved.")

        with st.expander("Weekend Mode", expanded=False):
            wm = cfg["settings"].get("weekend_mode", {})
            with st.form("weekend_mode_form"):
                enabled = st.checkbox("Enable weekend mode", value=wm.get("enabled", False))
                col1, col2 = st.columns(2)
                with col1:
                    threshold = st.slider(
                        "Similarity threshold (best matches)",
                        0.0, 1.0, float(wm.get("similarity_threshold", 0.45)), step=0.01,
                    )
                    max_top = st.slider("Max top-match stories", 5, 30, int(wm.get("max_top_matches", 10)))
                    title = st.text_input("Digest title", value=wm.get("digest_title", "Weekend Reads"))
                with col2:
                    interesting_count = st.slider(
                        "Interesting reads count", 5, 30, int(wm.get("interesting_reads_count", 10))
                    )
                    interesting_min = st.slider(
                        "Min HN score for interesting reads", 50, 500, int(wm.get("interesting_min_score", 100))
                    )
                if st.form_submit_button("Save weekend mode"):
                    cfg["settings"]["weekend_mode"] = {
                        "enabled": enabled,
                        "apply_on": ["sat", "sun"],
                        "similarity_threshold": threshold,
                        "max_top_matches": max_top,
                        "interesting_reads_count": interesting_count,
                        "interesting_min_score": interesting_min,
                        "digest_title": title,
                    }
                    save_config(cfg)
                    st.success("Weekend mode saved.")

        with st.expander("Followed HN Users", expanded=False):
            followed = cfg["settings"].get("followed_hn_users", [])
            with st.form("followed_users_form"):
                new_user = st.text_input("Add HN username")
                if followed:
                    to_remove = st.multiselect(
                        "Remove users", followed,
                        help="Select users to unfollow, then save."
                    )
                    st.caption("Currently following: " + ", ".join(
                        f"[{u}](https://news.ycombinator.com/user?id={u})" for u in followed
                    ))
                else:
                    to_remove = []
                    st.caption("No users followed yet. Add a username above.")
                if st.form_submit_button("Save"):
                    updated = [u for u in followed if u not in to_remove]
                    username = new_user.strip()
                    if username and username not in updated:
                        updated.append(username)
                    cfg["settings"]["followed_hn_users"] = updated
                    save_config(cfg)
                    st.success("Followed users saved.")

        st.caption(f"Config file: `{CONFIG_PATH}`")


    # ── Engg Tab 4: Simulator ─────────────────────────────────────────────────

    with tabs[3]:
        st.header("Simulator")
        st.caption("Preview how a URL or text would match topics and appear in a digest.")

        url_input = st.text_input("URL (optional — will fetch title)")
        text_input = st.text_area("Or paste raw text / title", height=100)

        if st.button("Run simulator", type="primary"):
            text_to_match = text_input.strip()

            if url_input.strip() and not text_to_match:
                with st.spinner("Fetching page title…"):
                    try:
                        req = urllib.request.Request(
                            url_input.strip(),
                            headers={"User-Agent": "Mozilla/5.0 knowledge-os/1.0"},
                        )
                        with urllib.request.urlopen(req, timeout=8) as resp:
                            html = resp.read(32768).decode("utf-8", errors="ignore")
                        import re
                        m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
                        text_to_match = m.group(1).strip() if m else url_input.strip()
                        st.info(f"Using title: **{text_to_match}**")
                    except Exception as e:
                        text_to_match = url_input.strip()
                        st.warning(f"Could not fetch title ({e}). Using URL as text.")

            if not text_to_match:
                st.warning("Enter a URL or some text to simulate.")
            else:
                with st.spinner("Running topic matcher…"):
                    try:
                        matcher = get_topic_matcher()
                        story = {
                            "title": text_to_match,
                            "url": url_input.strip() or "https://example.com",
                            "score": 100,
                            "by": "simulator",
                            "id": 0,
                            "descendants": 0,
                            "time": datetime.now().timestamp(),
                            "fetched_at": datetime.now().isoformat(),
                            "source": "hackernews",
                        }
                        matched = matcher.match_stories([story])
                    except Exception as e:
                        st.error(f"Matcher error: {e}")
                        matched = []

                if not matched:
                    cfg_now = load_config()
                    thresh = cfg_now["settings"]["similarity_threshold"]
                    st.warning(
                        f"No topic matched above threshold ({thresh}). "
                        "This story would not appear in a digest."
                    )
                    try:
                        try:
                            from .match_topics import TopicMatcher
                        except ImportError:
                            from knowledge_os.match_topics import TopicMatcher
                        matcher2 = get_topic_matcher()
                        import numpy as np
                        story_emb = matcher2.model.encode([text_to_match])
                        all_scores = {}
                        for tname, temb in matcher2.topic_embeddings.items():
                            from sklearn.metrics.pairwise import cosine_similarity
                            s = cosine_similarity(story_emb, temb.reshape(1, -1))[0][0]
                            all_scores[tname] = float(s)
                        st.subheader("All topic scores (below threshold)")
                        st.bar_chart(pd.DataFrame.from_dict(all_scores, orient="index", columns=["score"]))
                    except Exception:
                        pass
                else:
                    m_story = matched[0]
                    best_topic = m_story["matched_topic"]
                    topic_score = m_story["topic_score"]
                    all_scores = m_story["all_topic_scores"]

                    c1, c2 = st.columns(2)
                    c1.metric("Best topic", best_topic)
                    c2.metric("Similarity score", f"{topic_score:.3f}")

                    st.subheader("All topic scores")
                    scores_df = pd.DataFrame.from_dict(all_scores, orient="index", columns=["score"])
                    scores_df = scores_df.sort_values("score", ascending=False)
                    st.bar_chart(scores_df)

                    st.subheader("Digest preview")
                    url_display = url_input.strip() or "https://example.com"
                    digest_block = f"""\
*{best_topic}*

- [ ] {text_to_match}
  ↑100 | 0 comments | by simulator
  🔗 {url_display}
  Notes: """
                    st.code(digest_block, language="markdown")
                    st.markdown("---")
                    st.markdown(f"**Rendered:**\n\n{digest_block}")

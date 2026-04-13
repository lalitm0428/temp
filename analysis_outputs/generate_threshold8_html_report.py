from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
from textwrap import dedent

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

MIN_POSTS = 8
MAX_BAR_COUNT = 8
SRC = Path('/Users/apple/temp/analysis_outputs/Updated-Genre-Data/Instagram_Genre_Emotion_Reach_Analysis.csv')
OUT = Path('/Users/apple/temp/analysis_outputs')
OUT.mkdir(exist_ok=True)


def clean_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if 'Genre.1' not in out.columns and 'genre' in out.columns:
        out['Genre.1'] = out['genre']
    if 'Emotions.1' not in out.columns and 'emotion' in out.columns:
        out['Emotions.1'] = out['emotion']
    if 'media_type' not in out.columns:
        out['media_type'] = 'post'
    if 'permalink' not in out.columns and 'permalink_url' in out.columns:
        out['permalink'] = out['permalink_url']
    if 'caption' not in out.columns and 'message' in out.columns:
        out['caption'] = out['message']

    numeric_cols = [
        'reach',
        'views',
        'likes',
        'comments',
        'shares',
        'saved',
        'total_interactions',
    ]
    for col in numeric_cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors='coerce')

    text_cols = ['Genre.1', 'Emotions.1', 'caption', 'permalink', 'post_created_date', 'media_type']
    for col in text_cols:
        if col in out.columns:
            out[col] = out[col].astype(str).str.strip()
            out[col] = out[col].replace({'nan': np.nan, 'None': np.nan, '': np.nan})

    out['post_date'] = pd.to_datetime(out.get('post_created_date'), errors='coerce')
    return out


def to_html_table(df: pd.DataFrame, max_rows: int = 25) -> str:
    if df.empty:
      return '<p class="muted">No rows to display.</p>'
    formatted = df.head(max_rows).copy()
    for col in formatted.columns:
      if is_percentage_column(col):
        formatted[col] = formatted[col].map(format_percentage_value)
    return formatted.to_html(index=False, classes='data-table', border=0, justify='left', escape=False)


def is_percentage_column(column_name: object) -> bool:
  col = str(column_name).strip().lower()
  return col.endswith('%') or 'pct' in col or 'percent' in col


def format_percentage_value(value: object) -> str:
  if value is None or (isinstance(value, float) and np.isnan(value)):
    return ''
  if isinstance(value, (int, np.integer, float, np.floating)):
    text = f"{float(value):.1f}".rstrip('0').rstrip('.')
    return f"{text}%"
  return str(value)


def make_plotly_block(fig, title: str, include_plotlyjs: bool = False) -> str:
    fig.update_layout(template='plotly_white', margin=dict(l=40, r=20, t=60, b=40), title=title)
    js_mode = 'inline' if include_plotlyjs else False
    return pio.to_html(fig, include_plotlyjs=js_mode, full_html=False)


def ascii_safe(text: object) -> str:
  return str(text).encode('ascii', 'ignore').decode('ascii')


def try_generate_pdf(html_path: Path, pdf_path: Path) -> tuple[bool, str]:
    chrome_candidates = [
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '/Applications/Chromium.app/Contents/MacOS/Chromium',
        shutil.which('google-chrome'),
        shutil.which('chromium'),
        shutil.which('chromium-browser'),
    ]
    chrome_binary = next((c for c in chrome_candidates if c and Path(c).exists()), None)
    if not chrome_binary:
        return False, 'Chrome/Chromium binary not found.'

    cmd = [
        chrome_binary,
        '--headless=new',
        '--disable-gpu',
        '--allow-file-access-from-files',
        '--no-pdf-header-footer',
        '--virtual-time-budget=12000',
        f'--print-to-pdf={str(pdf_path)}',
        html_path.resolve().as_uri(),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True, f'PDF generated at {pdf_path}'
    except subprocess.CalledProcessError as exc:
        err = (exc.stderr or exc.stdout or str(exc)).strip()
        return False, f'PDF generation failed: {err[:300]}'


def main() -> None:
    raw = pd.read_csv(SRC, low_memory=False)
    df = clean_frame(raw)

    labeled = df[df['reach'].notna() & df['Genre.1'].notna() & df['Emotions.1'].notna()].copy()

    genre_counts_all = (
        labeled.groupby('Genre.1', dropna=False)
        .size()
        .reset_index(name='posts')
        .sort_values('posts', ascending=False)
    )
    keep_genres = genre_counts_all[genre_counts_all['posts'] >= MIN_POSTS]['Genre.1'].tolist()
    removed_genres = genre_counts_all[genre_counts_all['posts'] < MIN_POSTS].copy()

    filtered_genre = labeled[labeled['Genre.1'].isin(keep_genres)].copy()

    combo_counts_all = (
        filtered_genre.groupby(['Genre.1', 'Emotions.1'], dropna=False)
        .size()
        .reset_index(name='posts')
        .sort_values('posts', ascending=False)
    )
    keep_combos = combo_counts_all[combo_counts_all['posts'] >= MIN_POSTS][['Genre.1', 'Emotions.1']].copy()
    removed_combos = combo_counts_all[combo_counts_all['posts'] < MIN_POSTS].copy()

    filtered_combo = filtered_genre.merge(keep_combos, on=['Genre.1', 'Emotions.1'], how='inner')

    benchmark_median = float(filtered_combo['reach'].median()) if len(filtered_combo) else float('nan')

    genre_stats = (
        filtered_combo.groupby('Genre.1')
        .agg(
            posts=('reach', 'size'),
        total_reach=('reach', 'sum'),
            median_reach=('reach', 'median'),
            mean_reach=('reach', 'mean'),
            p75_reach=('reach', lambda s: s.quantile(0.75)),
            max_reach=('reach', 'max'),
        )
        .reset_index()
        .sort_values('median_reach', ascending=False)
    )
    genre_stats['lift_vs_filtered_median_pct'] = (genre_stats['median_reach'] / benchmark_median - 1) * 100

    genre_hit = (
        filtered_combo.assign(above_median=(filtered_combo['reach'] >= benchmark_median))
        .groupby('Genre.1')
        .agg(posts=('reach', 'size'), pct_above_median=('above_median', 'mean'))
        .reset_index()
    )
    genre_hit['pct_above_median'] = genre_hit['pct_above_median'] * 100
    genre_hit = genre_hit.sort_values('pct_above_median', ascending=False)

    combo_stats = (
        filtered_combo.groupby(['Genre.1', 'Emotions.1'])
        .agg(
            posts=('reach', 'size'),
        total_reach=('reach', 'sum'),
            median_reach=('reach', 'median'),
            mean_reach=('reach', 'mean'),
            p75_reach=('reach', lambda s: s.quantile(0.75)),
            max_reach=('reach', 'max'),
        )
        .reset_index()
        .sort_values(['median_reach', 'posts'], ascending=[False, False])
    )
    combo_stats['lift_vs_filtered_median_pct'] = (combo_stats['median_reach'] / benchmark_median - 1) * 100

    top_5_genres = genre_stats.head(5).copy()
    top_10_combos = combo_stats.head(10).copy()

    # Pareto analysis by reach contribution
    pareto_genre = genre_stats[['Genre.1', 'posts', 'total_reach']].copy()
    pareto_genre = pareto_genre.sort_values('total_reach', ascending=False)
    genre_total_reach = float(pareto_genre['total_reach'].sum()) if len(pareto_genre) else 0.0
    if genre_total_reach > 0:
      pareto_genre['reach_share_pct'] = (pareto_genre['total_reach'] / genre_total_reach) * 100
    else:
      pareto_genre['reach_share_pct'] = 0.0
    pareto_genre['cum_reach_pct'] = pareto_genre['reach_share_pct'].cumsum()
    genres_to_80 = int((pareto_genre['cum_reach_pct'] < 80).sum() + 1) if len(pareto_genre) else 0

    pareto_combo = combo_stats[['Genre.1', 'Emotions.1', 'posts', 'total_reach']].copy()
    pareto_combo = pareto_combo.sort_values('total_reach', ascending=False)
    combo_total_reach = float(pareto_combo['total_reach'].sum()) if len(pareto_combo) else 0.0
    if combo_total_reach > 0:
      pareto_combo['reach_share_pct'] = (pareto_combo['total_reach'] / combo_total_reach) * 100
    else:
      pareto_combo['reach_share_pct'] = 0.0
    pareto_combo['cum_reach_pct'] = pareto_combo['reach_share_pct'].cumsum()
    combos_to_80 = int((pareto_combo['cum_reach_pct'] < 80).sum() + 1) if len(pareto_combo) else 0
    pareto_combo_80 = pareto_combo.head(combos_to_80).copy()

    top_5_genres = top_5_genres.merge(
        genre_hit[['Genre.1', 'pct_above_median']],
        on='Genre.1',
        how='left',
    )

    post_cols = [
        'post_created_date',
        'reach',
        'Genre.1',
        'Emotions.1',
        'caption',
        'permalink',
        'likes',
        'comments',
        'shares',
        'saved',
        'total_interactions',
    ]
    for col in post_cols:
        if col not in filtered_combo.columns:
            filtered_combo[col] = np.nan

    posts = filtered_combo[post_cols].copy()
    posts['caption_short'] = posts['caption'].astype(str).map(lambda x: ascii_safe(' '.join(x.split())[:140]))
    posts['Genre.1'] = posts['Genre.1'].astype(str).map(ascii_safe)
    posts['Emotions.1'] = posts['Emotions.1'].astype(str).map(ascii_safe)
    posts['permalink'] = posts['permalink'].map(lambda u: f'<a href="{u}" target="_blank">link</a>' if isinstance(u, str) and u.startswith('http') else '')

    top_posts = posts.sort_values('reach', ascending=False).head(10)

    # Save filtered data artifacts
    pd.DataFrame(
        [
            {
                'min_posts_threshold': MIN_POSTS,
                'rows_total': len(df),
                'rows_labeled': len(labeled),
                'rows_after_genre_filter': len(filtered_genre),
                'rows_after_genre_emotion_filter': len(filtered_combo),
                'filtered_benchmark_median_reach': benchmark_median,
                'kept_genres_count': len(keep_genres),
                'kept_genre_emotion_count': len(combo_stats),
                'removed_genres_count': len(removed_genres),
                'removed_genre_emotion_count': len(removed_combos),
            }
        ]
    ).to_csv(OUT / 'summary_metrics_8plus.csv', index=False)

    genre_counts_all.to_csv(OUT / 'genre_counts_all.csv', index=False)
    removed_genres.to_csv(OUT / 'removed_genres_lt8.csv', index=False)
    combo_counts_all.to_csv(OUT / 'genre_emotion_counts_after_genre_filter.csv', index=False)
    removed_combos.to_csv(OUT / 'removed_genre_emotion_lt8.csv', index=False)
    genre_stats.to_csv(OUT / 'genre_stats_8plus.csv', index=False)
    genre_hit.to_csv(OUT / 'genre_hit_rate_8plus.csv', index=False)
    combo_stats.to_csv(OUT / 'genre_emotion_stats_8plus.csv', index=False)
    pareto_genre.to_csv(OUT / 'pareto_genre_8plus.csv', index=False)
    pareto_combo.to_csv(OUT / 'pareto_genre_emotion_8plus.csv', index=False)
    top_posts.to_csv(OUT / 'top_posts_8plus.csv', index=False)

    # Charts
    genre_chart_data = genre_stats.sort_values('median_reach', ascending=False).head(MAX_BAR_COUNT).copy()
    fig_genre = px.bar(
      genre_chart_data.sort_values('median_reach', ascending=True),
        x='median_reach',
        y='Genre.1',
        orientation='h',
        text='posts',
        color='median_reach',
        color_continuous_scale='Tealgrn',
        labels={'median_reach': 'Median Reach', 'Genre.1': 'Genre', 'posts': 'Posts'},
    )

    pareto_genre_chart = pareto_genre.head(MAX_BAR_COUNT).copy()
    fig_pareto = make_subplots(specs=[[{"secondary_y": True}]])
    fig_pareto.add_trace(
      go.Bar(
        x=pareto_genre_chart['Genre.1'],
        y=pareto_genre_chart['reach_share_pct'],
        name='Reach Share %',
        marker_color='#1d4ed8',
      ),
      secondary_y=False,
    )
    fig_pareto.add_trace(
      go.Scatter(
        x=pareto_genre_chart['Genre.1'],
        y=pareto_genre_chart['cum_reach_pct'],
        mode='lines+markers',
        name='Cumulative Reach %',
        line=dict(color='#0f766e', width=3),
        marker=dict(size=7),
      ),
      secondary_y=True,
    )
    fig_pareto.add_hline(y=80, line_dash='dash', line_color='#ef4444', annotation_text='Pareto 80%')
    max_share = float(pareto_genre['reach_share_pct'].max()) if len(pareto_genre) else 40
    fig_pareto.update_yaxes(title_text='Reach Share %', secondary_y=False, range=[0, max(40, max_share * 1.25)])
    fig_pareto.update_yaxes(title_text='Cumulative Reach %', secondary_y=True, range=[0, 105])
    fig_pareto.update_xaxes(title_text='Genre')

    top_combo_median_chart = combo_stats.head(MAX_BAR_COUNT).copy()
    top_combo_median_chart['combo'] = top_combo_median_chart.apply(
      lambda row: f"{row['Genre.1']} | {row['Emotions.1']}", axis=1
    )
    fig_combo_median = px.bar(
      top_combo_median_chart.sort_values('median_reach', ascending=True),
      x='median_reach',
      y='combo',
      orientation='h',
      text='posts',
      color='median_reach',
      color_continuous_scale='Viridis',
      labels={'median_reach': 'Median Reach', 'combo': 'Genre | Emotion', 'posts': 'Posts'},
    )

    top_combo_share_chart = pareto_combo.head(MAX_BAR_COUNT).copy()
    top_combo_share_chart['combo'] = top_combo_share_chart.apply(
      lambda row: f"{row['Genre.1']} | {row['Emotions.1']}", axis=1
    )
    fig_combo_share = px.bar(
      top_combo_share_chart.sort_values('reach_share_pct', ascending=True),
      x='reach_share_pct',
      y='combo',
      orientation='h',
      text=top_combo_share_chart.sort_values('reach_share_pct', ascending=True)['reach_share_pct'].round(2),
      color='reach_share_pct',
      color_continuous_scale='Blues',
      labels={'reach_share_pct': 'Reach Share %', 'combo': 'Genre | Emotion'},
    )

    insights = [
        f"Threshold applied: keep only rows from genres and genre-emotion pairs with >= {MIN_POSTS} posts.",
        f"Rows considered after filters: {len(filtered_combo):,} (from {len(labeled):,} labeled rows).",
        f"Filtered benchmark median reach: {benchmark_median:,.1f}.",
        f"Genres retained: {len(keep_genres)}. Genre-emotion pairs retained: {len(combo_stats)}.",
      f"Pareto: top {genres_to_80} genres account for ~80% of retained reach.",
      f"Pareto: top {combos_to_80} genre x emotion buckets account for ~80% of retained reach.",
    ]

    html = f"""
<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Reach Report (8+ Posts Filter)</title>
  <style>
    :root {{
      --bg: #f5f7fb;
      --card: #ffffff;
      --ink: #102a43;
      --muted: #5c6b7a;
      --accent: #0f766e;
      --accent-2: #1d4ed8;
      --border: #d9e2ec;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: radial-gradient(circle at 10% 0%, #d7f2ee 0%, #f5f7fb 35%, #eff4ff 100%); font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; color: var(--ink); }}
    .wrap {{ max-width: 1300px; margin: 0 auto; padding: 28px 20px 36px; }}
    .hero {{ background: linear-gradient(135deg, #0f766e 0%, #1d4ed8 100%); color: #fff; border-radius: 18px; padding: 26px 26px 24px; box-shadow: 0 12px 30px rgba(16,42,67,.18); }}
    .hero h1 {{ margin: 0; font-size: 30px; line-height: 1.2; }}
    .hero p {{ margin: 10px 0 0; font-size: 15px; opacity: .95; }}
    .grid {{ display: grid; gap: 14px; margin-top: 16px; grid-template-columns: repeat(4, minmax(0, 1fr)); }}
    .kpi {{ background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.22); border-radius: 12px; padding: 12px; }}
    .kpi .k {{ font-size: 12px; text-transform: uppercase; letter-spacing: .05em; opacity: .9; }}
    .kpi .v {{ font-size: 24px; font-weight: 700; margin-top: 4px; }}
    .section {{ margin-top: 18px; background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 16px; box-shadow: 0 8px 22px rgba(15,23,42,.06); }}
    .section h2 {{ margin: 0 0 10px; font-size: 20px; color: #0b3c5d; }}
    .two {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
    .muted {{ color: var(--muted); font-size: 14px; }}
    ul {{ margin: 8px 0 0 18px; }}
    li {{ margin: 4px 0; }}
    .data-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    .data-table th, .data-table td {{ border-bottom: 1px solid var(--border); padding: 8px; text-align: left; vertical-align: top; }}
    .data-table th {{ background: #f7fafc; font-weight: 700; }}
    .chip {{ display: inline-block; padding: 4px 10px; border-radius: 999px; background: #e6fffa; color: #065f46; border: 1px solid #99f6e4; font-size: 12px; margin-right: 6px; }}
    .actions {{ margin-top: 10px; }}
    .btn {{ background: #0f766e; color: #fff; border: 0; padding: 10px 14px; border-radius: 10px; cursor: pointer; font-weight: 600; }}
    .btn:hover {{ background: #0b5c56; }}
    .page-break {{ break-before: page; page-break-before: always; }}
    @media print {{
      body {{ background: #fff !important; print-color-adjust: exact; -webkit-print-color-adjust: exact; }}
      .wrap {{ max-width: 100%; padding: 0; }}
      .section, .hero {{ box-shadow: none; border: 1px solid #d1d5db; }}
      .no-print {{ display: none !important; }}
      .data-table {{ font-size: 11px; }}
      .data-table th, .data-table td {{ padding: 5px; }}
    }}
    @media (max-width: 1050px) {{
      .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .two {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 680px) {{
      .grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <section class=\"hero\">
      <h1>Reach Report: Genre and Genre x Emotion (8+ Post Filter)</h1>
      <p>Only genres and genre-emotion combinations with at least {MIN_POSTS} posts are included in scoring and recommendations.</p>
      <div class=\"actions no-print\">
        <button class=\"btn\" onclick=\"window.print()\">Print / Save as PDF</button>
      </div>
      <div class=\"grid\">
        <div class=\"kpi\"><div class=\"k\">Labeled Rows</div><div class=\"v\">{len(labeled):,}</div></div>
        <div class=\"kpi\"><div class=\"k\">Rows After 8+ Filters</div><div class=\"v\">{len(filtered_combo):,}</div></div>
        <div class=\"kpi\"><div class=\"k\">Filtered Median Reach</div><div class=\"v\">{benchmark_median:,.0f}</div></div>
        <div class=\"kpi\"><div class=\"k\">Kept Genre x Emotion Pairs</div><div class=\"v\">{len(combo_stats):,}</div></div>
      </div>
    </section>

    <section class=\"section\">
      <h2>Filter Impact</h2>
      <p class=\"muted\">This run removes sparse buckets to avoid misleading conclusions from tiny sample sizes.</p>
      <span class=\"chip\">Genres removed (&lt;8 posts): {len(removed_genres)}</span>
      <span class=\"chip\">Genre x Emotion removed (&lt;8 posts): {len(removed_combos)}</span>
      <span class=\"chip\">Pareto 80%: Top {genres_to_80} Genres</span>
      <span class=\"chip\">Pareto 80%: Top {combos_to_80} Genre x Emotion</span>
      <ul>
        {''.join(f'<li>{i}</li>' for i in insights)}
      </ul>
    </section>

    <section class=\"section two\">
      <div>
        <h2>Genre Median Reach</h2>
        {make_plotly_block(fig_genre, 'Median Reach by Genre (Filtered)', include_plotlyjs=True)}
      </div>
      <div>
        <h2>Pareto: Reach Contribution by Genre</h2>
        {make_plotly_block(fig_pareto, 'Pareto Chart (Bars = Reach Share, Line = Cumulative %)')}
      </div>
    </section>

    <section class="section two">
      <div>
        <h2>Genre x Emotion: Top by Median Reach</h2>
        {make_plotly_block(fig_combo_median, 'Top 8 Genre x Emotion by Median Reach')}
      </div>
      <div>
        <h2>Genre x Emotion: Top by Reach Share</h2>
        {make_plotly_block(fig_combo_share, 'Top 8 Genre x Emotion by Reach Share %')}
      </div>
    </section>

    <section class=\"section two page-break\">
      <div>
        <h2>Top 5 Genres</h2>
        {to_html_table(top_5_genres[['Genre.1', 'posts', 'median_reach', 'lift_vs_filtered_median_pct', 'pct_above_median']].rename(columns={'Genre.1': 'Genre', 'posts': 'Posts', 'median_reach': 'Median Reach', 'lift_vs_filtered_median_pct': 'Lift vs Median %', 'pct_above_median': 'Hit Rate %'}).round(1), 5)}
      </div>
      <div>
        <h2>Top 10 Genre x Emotion</h2>
        {to_html_table(top_10_combos[['Genre.1', 'Emotions.1', 'posts', 'median_reach', 'total_reach', 'lift_vs_filtered_median_pct']].rename(columns={'Genre.1': 'Genre', 'Emotions.1': 'Emotion', 'posts': 'Posts', 'median_reach': 'Median Reach', 'total_reach': 'Total Reach', 'lift_vs_filtered_median_pct': 'Lift vs Median %'}).round(1), 10)}
      </div>
    </section>

    <section class=\"section\">
      <h2>Pareto Buckets (Up to 80% Reach)</h2>
      <div class=\"two\">
        <div>
          <h3>Genres Driving 80% of Reach</h3>
          {to_html_table(pareto_genre.head(genres_to_80)[['Genre.1', 'posts', 'total_reach', 'reach_share_pct', 'cum_reach_pct']].rename(columns={'Genre.1': 'Genre', 'posts': 'Posts', 'total_reach': 'Total Reach', 'reach_share_pct': 'Reach Share %', 'cum_reach_pct': 'Cumulative %'}).round(2), 20)}
        </div>
        <div>
          <h3>Genre x Emotion Buckets Driving 80% of Reach</h3>
          {to_html_table(pareto_combo_80[['Genre.1', 'Emotions.1', 'posts', 'total_reach', 'reach_share_pct', 'cum_reach_pct']].rename(columns={'Genre.1': 'Genre', 'Emotions.1': 'Emotion', 'posts': 'Posts', 'total_reach': 'Total Reach', 'reach_share_pct': 'Reach Share %', 'cum_reach_pct': 'Cumulative %'}).round(2), 25)}
        </div>
      </div>
    </section>

    <section class=\"section\">
      <h2>Top Post Examples (Retained Buckets)</h2>
      <div>
        {to_html_table(top_posts[['post_created_date', 'reach', 'Genre.1', 'Emotions.1', 'caption_short', 'permalink']].rename(columns={'post_created_date': 'Date', 'reach': 'Reach', 'Genre.1': 'Genre', 'Emotions.1': 'Emotion', 'caption_short': 'Caption'}), 10)}
      </div>
    </section>

    <section class=\"section\">
      <h2>Removed Buckets for Transparency</h2>
      <div class=\"two\">
        <div>
          <h3>Removed Genres (&lt;8 posts)</h3>
          {to_html_table(removed_genres, 50)}
        </div>
        <div>
          <h3>Removed Genre x Emotion (&lt;8 posts)</h3>
          {to_html_table(removed_combos, 80)}
        </div>
      </div>
    </section>

  </div>
</body>
</html>
"""

    report_path = OUT / 'Reach_Genre_Emotion_Report_8plus.html'
    report_path.write_text(dedent(html), encoding='utf-8')

    pdf_path = OUT / 'Reach_Genre_Emotion_Report_8plus.pdf'
    pdf_ok, pdf_msg = try_generate_pdf(report_path, pdf_path)

    print('Generated:', report_path)
    print(pdf_msg)
    print('Kept genres:', len(keep_genres))
    print('Kept genre-emotion pairs:', len(combo_stats))
    print('Filtered median reach:', round(benchmark_median, 2))
    print('Pareto genres to 80%:', genres_to_80)
    print('Pareto genre-emotion to 80%:', combos_to_80)


if __name__ == '__main__':
    main()

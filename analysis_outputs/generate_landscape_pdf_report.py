from __future__ import annotations

import base64
import re
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from weasyprint import HTML

MIN_POSTS = 8
FALLBACK_THRESHOLDS = (8, 5, 4)
MIN_COMBO_BUCKETS = 4
NEUTRAL_MEDIAN_BAND = 750

SRC = Path('/Users/apple/temp/DH Social Media Metrics IG Base Data (1).csv')
OUT = Path('/Users/apple/temp/analysis_outputs')
CHARTS = OUT / 'charts'
LANGUAGE_REPORTS = OUT / 'language_reports'
OUT.mkdir(exist_ok=True)
CHARTS.mkdir(exist_ok=True)
LANGUAGE_REPORTS.mkdir(exist_ok=True)

HTML_PATH = OUT / 'Reach_Genre_Emotion_Report_8plus.html'
PDF_PATH = OUT / 'Reach_Genre_Emotion_Report_8plus.pdf'


def ascii_safe(text: object) -> str:
    return str(text).encode('ascii', 'ignore').decode('ascii')


def clean_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    numeric_cols = [
        'reach', 'views', 'likes', 'comments', 'shares', 'saved', 'total_interactions'
    ]
    for col in numeric_cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors='coerce')

    text_cols = [
        'Genre.1', 'Emotions.1', 'caption', 'permalink', 'post_created_date', 'media_type', 'language'
    ]
    for col in text_cols:
        if col in out.columns:
            out[col] = out[col].astype(str).str.strip()
            out[col] = out[col].replace({'nan': np.nan, 'None': np.nan, '': np.nan})

    out['post_date'] = pd.to_datetime(out.get('post_created_date'), format='%d-%b-%Y', errors='coerce')
    return out


def to_html_table(df: pd.DataFrame, max_rows: int = 25) -> str:
    if df.empty:
        return '<p class="muted">No rows to display.</p>'
    formatted = df.head(max_rows).copy()
    for col in formatted.columns:
        if pd.api.types.is_numeric_dtype(formatted[col]):
            formatted[col] = formatted[col].map(format_human_number)
    return formatted.to_html(index=False, classes='data-table', border=0, justify='left', escape=False)


def format_human_number(value: object) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ''
    if isinstance(value, (int, np.integer, float, np.floating)):
        n = float(value)
        sign = '-' if n < 0 else ''
        abs_n = abs(n)

        if abs_n >= 1_000_000:
            compact = f"{abs_n / 1_000_000:.1f}".rstrip('0').rstrip('.')
            return f"{sign}{compact}m"

        if abs_n >= 100_000:
            return f"{sign}{int(round(abs_n / 1_000))}k"

        if abs_n >= 1_000:
            compact = f"{abs_n / 1_000:.1f}".rstrip('0').rstrip('.')
            return f"{sign}{compact}k"

        return f"{int(round(n))}"
    return str(value)


def save_chart(fig: go.Figure, out_file: Path, width: int = 1600, height: int = 900) -> Path:
    fig.update_layout(template='plotly_white', margin=dict(l=45, r=25, t=65, b=45), font=dict(size=16))
    fig.write_image(str(out_file), width=width, height=height, scale=2)
    return out_file


def image_data_uri(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode('ascii')
    return f'data:image/png;base64,{b64}'


def chart_html_fragment(fig: go.Figure) -> str:
    return fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        config={'responsive': True, 'displaylogo': False},
    )


def format_date_range(series: pd.Series) -> str:
    valid = pd.to_datetime(series, errors='coerce').dropna()
    if valid.empty:
        return 'NA'
    return f"{valid.min().date().isoformat()} to {valid.max().date().isoformat()}"


def normalize_language(value: object) -> str:
    if pd.isna(value):
        return 'unknown'
    lang = str(value).strip().lower()
    if lang in {'', 'nan', 'none'}:
        return 'unknown'
    return lang


def safe_token(value: str) -> str:
    token = re.sub(r'[^a-z0-9]+', '_', value.lower()).strip('_')
    return token or 'unknown'


def filter_with_threshold(lang_df: pd.DataFrame, threshold: int) -> dict:
    genre_counts_all = (
        lang_df.groupby('Genre.1', dropna=False)
        .size().reset_index(name='posts')
        .sort_values('posts', ascending=False)
    )
    keep_genres = genre_counts_all[genre_counts_all['posts'] >= threshold]['Genre.1'].tolist()
    removed_genres = genre_counts_all[genre_counts_all['posts'] < threshold].copy()
    filtered_genre = lang_df[lang_df['Genre.1'].isin(keep_genres)].copy()

    combo_counts_all = (
        filtered_genre.groupby(['Genre.1', 'Emotions.1'], dropna=False)
        .size().reset_index(name='posts')
        .sort_values('posts', ascending=False)
    )
    keep_combos = combo_counts_all[combo_counts_all['posts'] >= threshold][['Genre.1', 'Emotions.1']].copy()
    removed_combos = combo_counts_all[combo_counts_all['posts'] < threshold].copy()

    filtered_combo = filtered_genre.merge(keep_combos, on=['Genre.1', 'Emotions.1'], how='inner')
    return {
        'threshold': threshold,
        'genre_counts_all': genre_counts_all,
        'removed_genres': removed_genres,
        'filtered_genre': filtered_genre,
        'combo_counts_all': combo_counts_all,
        'removed_combos': removed_combos,
        'keep_combos': keep_combos,
        'filtered_combo': filtered_combo,
    }


def pick_adaptive_threshold(lang_df: pd.DataFrame, min_combo_buckets: int = MIN_COMBO_BUCKETS) -> dict:
    best_non_empty = None

    for threshold in FALLBACK_THRESHOLDS:
        result = filter_with_threshold(lang_df, threshold)
        combo_bucket_count = len(result['keep_combos'])
        row_count = len(result['filtered_combo'])

        if row_count > 0:
            if best_non_empty is None:
                best_non_empty = result
            else:
                prev_combo_count = len(best_non_empty['keep_combos'])
                prev_row_count = len(best_non_empty['filtered_combo'])
                if (combo_bucket_count, row_count) > (prev_combo_count, prev_row_count):
                    best_non_empty = result

        if row_count > 0 and combo_bucket_count >= min_combo_buckets:
            return result

    if best_non_empty is not None:
        return best_non_empty

    return filter_with_threshold(lang_df, FALLBACK_THRESHOLDS[-1])


def build_language_payload(language: str, lang_df: pd.DataFrame) -> dict:
    threshold_result = pick_adaptive_threshold(lang_df)
    threshold = threshold_result['threshold']
    removed_genres = threshold_result['removed_genres']
    removed_combos = threshold_result['removed_combos']
    filtered_genre = threshold_result['filtered_genre']
    filtered_combo = threshold_result['filtered_combo']

    if filtered_combo.empty:
        return {
            'language': language,
            'threshold': threshold,
            'labeled_rows': len(lang_df),
            'labeled_date_range': format_date_range(lang_df['post_date']),
            'filtered_date_range': 'NA',
            'empty': True,
            'removed_genres': removed_genres,
            'removed_combos': removed_combos,
            'message': f'No analyzable rows for {language.upper()} even after fallback to threshold {threshold}.',
        }

    benchmark_median = float(filtered_combo['reach'].median())

    genre_stats = (
        filtered_combo.groupby('Genre.1')
        .agg(
            posts=('reach', 'size'),
            total_reach=('reach', 'sum'),
            median_reach=('reach', 'median'),
            mean_reach=('reach', 'mean')
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
    genre_hit['pct_above_median'] *= 100

    combo_stats = (
        filtered_combo.groupby(['Genre.1', 'Emotions.1'])
        .agg(
            posts=('reach', 'size'),
            total_reach=('reach', 'sum'),
            median_reach=('reach', 'median'),
            mean_reach=('reach', 'mean')
        )
        .reset_index()
        .sort_values(['median_reach', 'posts'], ascending=[False, False])
    )
    combo_stats['lift_vs_filtered_median_pct'] = (combo_stats['median_reach'] / benchmark_median - 1) * 100

    combo_stats_all_supply = (
        filtered_genre.groupby(['Genre.1', 'Emotions.1'])
        .agg(
            posts=('reach', 'size'),
            total_reach=('reach', 'sum'),
            median_reach=('reach', 'median')
        )
        .reset_index()
        .sort_values(['median_reach', 'posts'], ascending=[False, False])
    )
    combo_stats_all_supply['lift_vs_filtered_median_pct'] = (
        combo_stats_all_supply['median_reach'] / benchmark_median - 1
    ) * 100
    combo_stats_all_supply['median_gap'] = combo_stats_all_supply['median_reach'] - benchmark_median

    high_supply_performing = (
        combo_stats_all_supply[
            (combo_stats_all_supply['posts'] >= threshold)
            & (combo_stats_all_supply['median_gap'] > NEUTRAL_MEDIAN_BAND)
        ]
        .copy()
        .sort_values(['median_reach', 'posts'], ascending=[False, False])
    )
    high_supply_performing['action'] = 'Scale if possible / maintain'

    high_supply_neutral = (
        combo_stats_all_supply[
            (combo_stats_all_supply['posts'] >= threshold)
            & (combo_stats_all_supply['median_gap'].abs() <= NEUTRAL_MEDIAN_BAND)
        ]
        .copy()
        .sort_values(['posts', 'median_reach'], ascending=[False, False])
    )
    high_supply_neutral['action'] = 'Neutral / maintain posting cadence'

    high_supply_not_performing = (
        combo_stats_all_supply[
            (combo_stats_all_supply['posts'] >= threshold)
            & (combo_stats_all_supply['median_gap'] < -NEUTRAL_MEDIAN_BAND)
        ]
        .copy()
        .sort_values(['median_reach', 'posts'], ascending=[True, False])
    )
    high_supply_not_performing['action'] = 'Deep dive to identify reasons and improve performance'

    low_supply_performing = (
        combo_stats_all_supply[
            (combo_stats_all_supply['posts'] < threshold)
            & (combo_stats_all_supply['median_gap'] > NEUTRAL_MEDIAN_BAND)
        ]
        .copy()
        .sort_values(['median_reach', 'posts'], ascending=[False, False])
    )
    low_supply_performing['action'] = 'Experiment by increasing supply'

    pareto_genre = genre_stats[['Genre.1', 'posts', 'total_reach']].copy().sort_values('total_reach', ascending=False)
    total_genre_reach = float(pareto_genre['total_reach'].sum()) if len(pareto_genre) else 0.0
    pareto_genre['reach_share_pct'] = (pareto_genre['total_reach'] / total_genre_reach * 100) if total_genre_reach else 0.0
    pareto_genre['cum_reach_pct'] = pareto_genre['reach_share_pct'].cumsum()
    genres_to_80 = int((pareto_genre['cum_reach_pct'] < 80).sum() + 1) if len(pareto_genre) else 0

    pareto_combo = combo_stats[['Genre.1', 'Emotions.1', 'posts', 'total_reach']].copy().sort_values('total_reach', ascending=False)
    total_combo_reach = float(pareto_combo['total_reach'].sum()) if len(pareto_combo) else 0.0
    pareto_combo['reach_share_pct'] = (pareto_combo['total_reach'] / total_combo_reach * 100) if total_combo_reach else 0.0
    pareto_combo['cum_reach_pct'] = pareto_combo['reach_share_pct'].cumsum()
    combos_to_80 = int((pareto_combo['cum_reach_pct'] < 80).sum() + 1) if len(pareto_combo) else 0
    pareto_combo_80 = pareto_combo.head(combos_to_80)

    top_5_genres = genre_stats.head(5).merge(
        genre_hit[['Genre.1', 'pct_above_median']], on='Genre.1', how='left'
    )
    top_10_combos = combo_stats.head(10)

    posts = filtered_combo[['post_created_date', 'reach', 'Genre.1', 'Emotions.1', 'caption', 'permalink']].copy()
    posts['caption'] = posts['caption'].astype(str).map(lambda x: ascii_safe(' '.join(x.split())[:140]))
    posts['Genre.1'] = posts['Genre.1'].astype(str).map(ascii_safe)
    posts['Emotions.1'] = posts['Emotions.1'].astype(str).map(ascii_safe)
    posts['permalink'] = posts['permalink'].map(
        lambda u: f'<a href="{u}" target="_blank">link</a>' if isinstance(u, str) and u.startswith('http') else ''
    )

    top_posts = (
        posts.merge(top_10_combos[['Genre.1', 'Emotions.1']], on=['Genre.1', 'Emotions.1'], how='inner')
        .sort_values('reach', ascending=False)
        .head(10)
    )
    if top_posts.empty:
        top_posts = posts.sort_values('reach', ascending=False).head(10)

    bottom_posts = (
        posts.merge(
            high_supply_not_performing[['Genre.1', 'Emotions.1']].drop_duplicates(),
            on=['Genre.1', 'Emotions.1'],
            how='inner',
        )
        .sort_values('reach', ascending=True)
        .head(10)
    )
    if bottom_posts.empty:
        bottom_posts = posts.sort_values('reach', ascending=True).head(10)

    return {
        'language': language,
        'threshold': threshold,
        'labeled_rows': len(lang_df),
        'labeled_date_range': format_date_range(lang_df['post_date']),
        'filtered_rows': len(filtered_combo),
        'filtered_date_range': format_date_range(filtered_combo['post_date']),
        'benchmark_median': benchmark_median,
        'removed_genres': removed_genres,
        'removed_combos': removed_combos,
        'genre_stats': genre_stats,
        'genre_hit': genre_hit,
        'combo_stats': combo_stats,
        'high_supply_performing': high_supply_performing,
        'high_supply_neutral': high_supply_neutral,
        'high_supply_not_performing': high_supply_not_performing,
        'low_supply_performing': low_supply_performing,
        'pareto_genre': pareto_genre,
        'pareto_combo': pareto_combo,
        'pareto_combo_80': pareto_combo_80,
        'genres_to_80': genres_to_80,
        'combos_to_80': combos_to_80,
        'top_5_genres': top_5_genres,
        'top_10_combos': top_10_combos,
        'top_posts': top_posts,
        'bottom_posts': bottom_posts,
        'empty': False,
    }


def add_charts_to_payload(payload: dict) -> dict:
    if payload['empty']:
        payload['chart_uris'] = {}
        payload['chart_html'] = {}
        return payload

    lang = payload['language']
    slug = safe_token(lang)
    genre_stats = payload['genre_stats']
    pareto_genre = payload['pareto_genre']
    combo_stats = payload['combo_stats']
    pareto_combo = payload['pareto_combo']

    fig_genre = px.bar(
        genre_stats.sort_values('median_reach', ascending=True),
        x='median_reach', y='Genre.1', orientation='h', text='posts',
        color='median_reach', color_continuous_scale=['#fde68a', '#fb923c', '#f97316', '#c2410c'],
        labels={'median_reach': 'Median Reach', 'Genre.1': 'Genre'}
    )
    fig_genre.update_layout(title=f'Language {lang.upper()}: Genre Median Reach')

    fig_pareto = make_subplots(specs=[[{'secondary_y': True}]])
    fig_pareto.add_trace(
        go.Bar(
            x=pareto_genre['Genre.1'],
            y=pareto_genre['reach_share_pct'],
            name='Reach Share %',
            marker_color='#f97316'
        ),
        secondary_y=False,
    )
    fig_pareto.add_trace(
        go.Scatter(
            x=pareto_genre['Genre.1'],
            y=pareto_genre['cum_reach_pct'],
            mode='lines+markers',
            name='Cumulative Reach %',
            line=dict(color='#7e22ce', width=3)
        ),
        secondary_y=True,
    )
    fig_pareto.add_hline(y=80, line_dash='dash', line_color='#ef4444', annotation_text='80%')
    fig_pareto.update_yaxes(title_text='Reach Share %', secondary_y=False)
    fig_pareto.update_yaxes(title_text='Cumulative Reach %', secondary_y=True, range=[0, 105])
    fig_pareto.update_layout(title=f'Language {lang.upper()}: Pareto by Genre')

    top_combo_median = combo_stats.head(12).copy()
    top_combo_median['combo'] = top_combo_median.apply(lambda r: f"{r['Genre.1']} | {r['Emotions.1']}", axis=1)
    fig_combo_median = px.bar(
        top_combo_median.sort_values('median_reach', ascending=True),
        x='median_reach', y='combo', orientation='h', text='posts',
        color='median_reach', color_continuous_scale=['#fbcfe8', '#e879f9', '#a855f7', '#7e22ce'],
        labels={'median_reach': 'Median Reach', 'combo': 'Genre | Emotion'}
    )
    fig_combo_median.update_layout(title=f'Language {lang.upper()}: Genre x Emotion by Median Reach')

    top_combo_share = pareto_combo.head(12).copy()
    top_combo_share['combo'] = top_combo_share.apply(lambda r: f"{r['Genre.1']} | {r['Emotions.1']}", axis=1)
    fig_combo_share = px.bar(
        top_combo_share.sort_values('reach_share_pct', ascending=True),
        x='reach_share_pct', y='combo', orientation='h',
        text=top_combo_share.sort_values('reach_share_pct', ascending=True)['reach_share_pct'].round(0),
        color='reach_share_pct', color_continuous_scale=['#fde68a', '#fb923c', '#a855f7', '#6b21a8'],
        labels={'reach_share_pct': 'Reach Share %', 'combo': 'Genre | Emotion'}
    )
    fig_combo_share.update_layout(title=f'Language {lang.upper()}: Genre x Emotion by Reach Share')

    chart_files = {
        'genre_median': save_chart(fig_genre, CHARTS / f'{slug}_genre_median.png', 1500, 900),
        'genre_pareto': save_chart(fig_pareto, CHARTS / f'{slug}_genre_pareto.png', 1500, 900),
        'combo_median': save_chart(fig_combo_median, CHARTS / f'{slug}_combo_median.png', 1700, 1000),
        'combo_share': save_chart(fig_combo_share, CHARTS / f'{slug}_combo_share.png', 1700, 1000),
    }
    chart_figures = {
        'genre_median': fig_genre,
        'genre_pareto': fig_pareto,
        'combo_median': fig_combo_median,
        'combo_share': fig_combo_share,
    }
    payload['chart_uris'] = {k: image_data_uri(v) for k, v in chart_files.items()}
    payload['chart_html'] = {k: chart_html_fragment(v) for k, v in chart_figures.items()}
    return payload


def render_language_section(section: dict, idx: int) -> str:
    lang_label = section['language'].upper()
    threshold = section['threshold']
    page_break = '<div class="page-break"></div>' if idx > 0 else ''

    top_5_table = to_html_table(
        section['top_5_genres'][['Genre.1', 'posts', 'median_reach', 'total_reach', 'lift_vs_filtered_median_pct', 'pct_above_median']]
        .rename(columns={
            'Genre.1': 'Genre',
            'posts': 'Posts',
            'median_reach': 'Median Reach',
            'total_reach': 'Total Reach',
            'lift_vs_filtered_median_pct': 'Lift vs Median %',
            'pct_above_median': 'Hit Rate %',
        })
        .round(1),
        5,
    )

    top_10_table = to_html_table(
        section['top_10_combos'][['Genre.1', 'Emotions.1', 'posts', 'median_reach', 'total_reach', 'lift_vs_filtered_median_pct']]
        .rename(columns={
            'Genre.1': 'Genre',
            'Emotions.1': 'Emotion',
            'posts': 'Posts',
            'median_reach': 'Median Reach',
            'total_reach': 'Total Reach',
            'lift_vs_filtered_median_pct': 'Lift vs Median %',
        })
        .round(1),
        10,
    )

    pareto_genre_table = to_html_table(
        section['pareto_genre'].head(section['genres_to_80'])[['Genre.1', 'posts', 'total_reach', 'reach_share_pct', 'cum_reach_pct']]
        .rename(columns={
            'Genre.1': 'Genre',
            'posts': 'Posts',
            'total_reach': 'Total Reach',
            'reach_share_pct': 'Reach Share %',
            'cum_reach_pct': 'Cumulative %',
        })
        .round(2),
        25,
    )

    pareto_combo_table = to_html_table(
        section['pareto_combo_80'][['Genre.1', 'Emotions.1', 'posts', 'total_reach', 'reach_share_pct', 'cum_reach_pct']]
        .rename(columns={
            'Genre.1': 'Genre',
            'Emotions.1': 'Emotion',
            'posts': 'Posts',
            'total_reach': 'Total Reach',
            'reach_share_pct': 'Reach Share %',
            'cum_reach_pct': 'Cumulative %',
        })
        .round(2),
        25,
    )

    top_posts_table = to_html_table(
        section['top_posts'][['post_created_date', 'reach', 'Genre.1', 'Emotions.1', 'caption', 'permalink']]
        .rename(columns={
            'post_created_date': 'Date',
            'reach': 'Reach',
            'Genre.1': 'Genre',
            'Emotions.1': 'Emotion',
            'caption': 'Caption',
        }),
        10,
    )

    supply_columns = ['Genre.1', 'Emotions.1', 'posts', 'median_reach', 'lift_vs_filtered_median_pct', 'action']
    supply_rename = {
        'Genre.1': 'Genre',
        'Emotions.1': 'Emotion',
        'posts': 'Posts',
        'median_reach': 'Median Reach',
        'lift_vs_filtered_median_pct': 'Lift vs Median %',
        'action': 'Recommended Action',
    }

    high_supply_performing_table = to_html_table(
        section['high_supply_performing'][supply_columns].rename(columns=supply_rename),
        8,
    )
    high_supply_neutral_table = to_html_table(
        section['high_supply_neutral'][supply_columns].rename(columns=supply_rename),
        8,
    )
    high_supply_not_performing_table = to_html_table(
        section['high_supply_not_performing'][supply_columns].rename(columns=supply_rename),
        8,
    )
    low_supply_performing_table = to_html_table(
        section['low_supply_performing'][supply_columns].rename(columns=supply_rename),
        8,
    )

    bottom_posts_table = to_html_table(
        section['bottom_posts'][['post_created_date', 'reach', 'Genre.1', 'Emotions.1', 'caption', 'permalink']]
        .rename(columns={
            'post_created_date': 'Date',
            'reach': 'Reach',
            'Genre.1': 'Genre',
            'Emotions.1': 'Emotion',
            'caption': 'Caption',
        }),
        10,
    )

    return f"""
    {page_break}
    <section class="section">
      <h2>Language: {lang_label}</h2>
      <span class="chip">Selected threshold: {threshold} posts</span>
            <span class="chip">Labeled rows: {format_human_number(section['labeled_rows'])}</span>
            <span class="chip">Rows after filters: {format_human_number(section['filtered_rows'])}</span>
    <span class="chip">Labeled date range: {section['labeled_date_range']}</span>
    <span class="chip">Filtered date range: {section['filtered_date_range']}</span>
            <span class="chip">Filtered median reach: {format_human_number(section['benchmark_median'])}</span>
      <span class="chip">Removed genres (&lt;{threshold}): {len(section['removed_genres'])}</span>
      <span class="chip">Removed genre x emotion (&lt;{threshold}): {len(section['removed_combos'])}</span>
      <span class="chip">Pareto 80% genres: {section['genres_to_80']}</span>
      <span class="chip">Pareto 80% genre x emotion: {section['combos_to_80']}</span>
            <div class="metric-row">
                <div class="metric-card">
                    <div class="metric-k">Median Reach Benchmark (lift baseline)</div>
                    <div class="metric-v">{format_human_number(section['benchmark_median'])}</div>
                </div>
            </div>
    </section>

    <section class="section two">
      <div class="chart">
        <h3>{lang_label}: Genre Median Reach</h3>
                <div class="chart-interactive">{section['chart_html']['genre_median']}</div>
                <img class="chart-static" src="{section['chart_uris']['genre_median']}" alt="{lang_label} Genre Median Reach" />
      </div>
      <div class="chart">
        <h3>{lang_label}: Pareto by Genre</h3>
                <div class="chart-interactive">{section['chart_html']['genre_pareto']}</div>
                <img class="chart-static" src="{section['chart_uris']['genre_pareto']}" alt="{lang_label} Pareto by Genre" />
      </div>
    </section>

    <section class="section two">
      <div class="chart">
        <h3>{lang_label}: Genre x Emotion by Median Reach</h3>
                <div class="chart-interactive">{section['chart_html']['combo_median']}</div>
                <img class="chart-static" src="{section['chart_uris']['combo_median']}" alt="{lang_label} Genre x Emotion Median" />
      </div>
      <div class="chart">
        <h3>{lang_label}: Genre x Emotion by Reach Share</h3>
                <div class="chart-interactive">{section['chart_html']['combo_share']}</div>
                <img class="chart-static" src="{section['chart_uris']['combo_share']}" alt="{lang_label} Genre x Emotion Reach Share" />
      </div>
    </section>

        <section class="section">
            <h2>{lang_label}: Supply x Performance Actions</h2>
            <div class="two">
                <div>
                    <h3>Genre x Emotion with Supply and Performing</h3>
                    {high_supply_performing_table}
                </div>
                <div>
                    <h3>Genre x Emotion with Supply and Neutral</h3>
                    {high_supply_neutral_table}
                </div>
            </div>
            <div class="two" style="margin-top:10px;">
                <div>
                    <h3>Genre x Emotion with Supply and Not Performing</h3>
                    {high_supply_not_performing_table}
                </div>
                <div>
                    <h3>Genre x Emotion with Low Supply and Performing</h3>
                    {low_supply_performing_table}
                </div>
            </div>
        </section>

    <section class="section">
      <h2>{lang_label}: Top Tables</h2>
      <div class="two">
        <div>
          <h3>Top 5 Genres</h3>
          {top_5_table}
        </div>
        <div>
          <h3>Top 10 Genre x Emotion</h3>
          {top_10_table}
        </div>
      </div>
    </section>

    <section class="section">
      <h2>{lang_label}: Pareto 80% Buckets</h2>
      <div class="two">
        <div>
          <h3>Genres to 80%</h3>
          {pareto_genre_table}
        </div>
        <div>
          <h3>Genre x Emotion to 80%</h3>
          {pareto_combo_table}
        </div>
      </div>
    </section>

    <section class="section">
      <h2>{lang_label}: Top Post Examples</h2>
      {top_posts_table}
    </section>

        <section class="section">
            <h2>{lang_label}: Bottom Post Examples (Supply and Not Performing)</h2>
            {bottom_posts_table}
        </section>
    """


def build_single_language_html(section: dict) -> str:
        language_label = section['language'].upper()
        section_html = render_language_section(section, 0)

        return f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Reach Report ({language_label})</title>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <style>
        @page {{ size: A4 landscape; margin: 10mm; }}
        * {{ box-sizing: border-box; }}
        body {{ font-family: 'Helvetica Neue', Arial, sans-serif; color: #102a43; margin: 0; background: #edf1f5; }}
        .wrap {{ max-width: 1700px; margin: 0 auto; padding: 16px; }}
        .top-nav {{ margin-bottom: 10px; }}
        .back-link {{ display: inline-block; text-decoration: none; font-size: 13px; font-weight: 600; color: #7a2f0b; background: #fff1e8; border: 1px solid #f8b58a; border-radius: 999px; padding: 8px 12px; }}
        .back-link:hover {{ background: #ffe9db; }}
        .hero {{ background: linear-gradient(135deg, #f97316 0%, #7e22ce 100%); color: #fff; border-radius: 14px; padding: 16px; box-shadow: 0 2px 10px rgba(16, 42, 67, 0.08); }}
        .hero h1 {{ margin: 0 0 4px 0; font-size: 24px; }}
        .hero p {{ margin: 0; font-size: 13px; }}
        .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-top: 10px; }}
        .kpi {{ background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.25); border-radius: 8px; padding: 8px; }}
        .kpi .k {{ font-size: 10px; text-transform: uppercase; opacity: .9; }}
        .kpi .v {{ font-size: 20px; font-weight: 700; margin-top: 2px; }}
                .section {{ margin-top: 12px; border: 1px solid #cfd9e5; border-radius: 14px; padding: 12px; background: #f7f9fc; page-break-inside: auto; break-inside: auto; }}
        .section h2 {{ margin: 0 0 6px 0; font-size: 18px; color: #0b3c5d; }}
        .two {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
        .chart {{ border: 1px solid #dbe4ee; border-radius: 12px; padding: 8px; background: #fff; }}
        .chart h3 {{ margin: 0 0 6px 0; font-size: 14px; }}
        .chart-interactive .plotly-graph-div {{ width: 100% !important; height: 420px !important; }}
        .chart-static {{ display: none; width: 100%; height: auto; }}
                .chart, .kpi, .chip {{ page-break-inside: avoid; break-inside: avoid; }}
        .data-table {{ width: 100%; border-collapse: collapse; font-size: 10px; table-layout: fixed; }}
        .data-table th, .data-table td {{ border-bottom: 1px solid #d9e2ec; padding: 4px; text-align: left; vertical-align: top; word-wrap: break-word; }}
                .data-table tr {{ page-break-inside: avoid; break-inside: avoid; }}
        .data-table th {{ background: #edf3f9; font-weight: 700; }}
        .chip {{ display: inline-block; padding: 2px 10px; border-radius: 999px; border: 1px solid #f8b58a; background: #fff1e8; color: #7a2f0b; font-size: 10px; margin: 0 6px 6px 0; }}
        .metric-row {{ margin-top: 10px; }}
        .metric-card {{ display: inline-block; min-width: 240px; border: 1px solid #d8c4f2; border-radius: 12px; background: linear-gradient(135deg, #fff1e8, #f5ebff); padding: 8px 12px; }}
        .metric-k {{ font-size: 10px; color: #5b4c6f; text-transform: uppercase; }}
        .metric-v {{ font-size: 20px; font-weight: 700; color: #2f1f45; margin-top: 2px; }}
        .muted {{ color: #5c6b7a; font-size: 12px; }}
                @media print {{
                    .top-nav {{ display: none !important; }}
                    .two {{ display: block; }}
                    .two > div {{ margin-bottom: 10px; }}
                    .chart-interactive {{ display: none !important; }}
                    .chart-static {{ display: block !important; max-height: 105mm; object-fit: contain; }}
                }}
    </style>
</head>
<body>
    <div class="wrap">
        <nav class="top-nav">
            <a class="back-link" href="/analysis_outputs/Report_Navigation.html">&larr; Back to Report Navigation</a>
        </nav>
        <section class="hero">
            <h1>Reach Report: {language_label}</h1>
            <p>Standalone language report with adaptive thresholding (8 -> 5 -> 4).</p>
            <div class="grid">
                <div class="kpi"><div class="k">Language</div><div class="v">{language_label}</div></div>
                <div class="kpi"><div class="k">Labeled Rows</div><div class="v">{format_human_number(section['labeled_rows'])}</div></div>
                <div class="kpi"><div class="k">Rows After Filters</div><div class="v">{format_human_number(section['filtered_rows'])}</div></div>
                <div class="kpi"><div class="k">Threshold Used</div><div class="v">{section['threshold']}</div></div>
            </div>
            <p style="margin-top:8px;font-size:12px;">
                Labeled date range: {section['labeled_date_range']}<br />
                Filtered date range: {section['filtered_date_range']}
            </p>
        </section>

        {section_html}
    </div>
</body>
</html>
"""


def main() -> None:
    df = clean_frame(pd.read_csv(SRC, low_memory=False))
    df['language_norm'] = df.get('language', 'unknown').map(normalize_language)
    labeled = df[df['reach'].notna() & df['Genre.1'].notna() & df['Emotions.1'].notna()].copy()

    language_counts = labeled['language_norm'].value_counts()
    languages = language_counts.index.tolist()

    language_sections = []
    skipped_languages = []

    for language in languages:
        lang_df = labeled[labeled['language_norm'] == language].copy()
        payload = build_language_payload(language, lang_df)
        payload = add_charts_to_payload(payload)

        if payload['empty']:
            skipped_languages.append(language)
            continue

        slug = safe_token(language)
        payload['genre_stats'].assign(language=language).to_csv(OUT / f'genre_stats_lang_{slug}.csv', index=False)
        payload['combo_stats'].assign(language=language).to_csv(OUT / f'genre_emotion_stats_lang_{slug}.csv', index=False)
        payload['pareto_genre'].assign(language=language).to_csv(OUT / f'pareto_genre_lang_{slug}.csv', index=False)
        payload['pareto_combo'].assign(language=language).to_csv(OUT / f'pareto_genre_emotion_lang_{slug}.csv', index=False)
        language_sections.append(payload)

    if not language_sections:
        raise ValueError('No language had analyzable rows after adaptive threshold fallback.')

    all_genre_stats = pd.concat([s['genre_stats'].assign(language=s['language']) for s in language_sections], ignore_index=True)
    all_combo_stats = pd.concat([s['combo_stats'].assign(language=s['language']) for s in language_sections], ignore_index=True)
    all_pareto_genre = pd.concat([s['pareto_genre'].assign(language=s['language']) for s in language_sections], ignore_index=True)
    all_pareto_combo = pd.concat([s['pareto_combo'].assign(language=s['language']) for s in language_sections], ignore_index=True)

    all_genre_stats.to_csv(OUT / 'genre_stats_8plus.csv', index=False)
    all_combo_stats.to_csv(OUT / 'genre_emotion_stats_8plus.csv', index=False)
    all_pareto_genre.to_csv(OUT / 'pareto_genre_8plus.csv', index=False)
    all_pareto_combo.to_csv(OUT / 'pareto_genre_emotion_8plus.csv', index=False)

    total_labeled_rows = int(sum(s['labeled_rows'] for s in language_sections))
    total_filtered_rows = int(sum(s['filtered_rows'] for s in language_sections))
    total_kept_combos = int(sum(len(s['combo_stats']) for s in language_sections))
    overall_labeled_date_range = format_date_range(labeled['post_date'])

    threshold_overview = ', '.join(f"{s['language'].upper()}={s['threshold']}" for s in language_sections)
    skipped_text = ', '.join(x.upper() for x in skipped_languages) if skipped_languages else 'None'

    sections_html = ''.join(render_language_section(section, idx) for idx, section in enumerate(language_sections))

    html = f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Reach Report by Language (Adaptive 8/5/4)</title>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    @page {{ size: A4 landscape; margin: 10mm; }}
    * {{ box-sizing: border-box; }}
    body {{ font-family: 'Helvetica Neue', Arial, sans-serif; color: #102a43; margin: 0; background: #edf1f5; }}
    .wrap {{ max-width: 1700px; margin: 0 auto; padding: 16px; }}
    .top-nav {{ margin-bottom: 10px; }}
    .back-link {{ display: inline-block; text-decoration: none; font-size: 13px; font-weight: 600; color: #7a2f0b; background: #fff1e8; border: 1px solid #f8b58a; border-radius: 999px; padding: 8px 12px; }}
    .back-link:hover {{ background: #ffe9db; }}
    .hero {{ background: linear-gradient(135deg, #f97316 0%, #7e22ce 100%); color: #fff; border-radius: 14px; padding: 16px; box-shadow: 0 2px 10px rgba(16, 42, 67, 0.08); }}
    .hero h1 {{ margin: 0 0 4px 0; font-size: 24px; }}
    .hero p {{ margin: 0; font-size: 13px; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-top: 10px; }}
    .kpi {{ background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.25); border-radius: 8px; padding: 8px; }}
    .kpi .k {{ font-size: 10px; text-transform: uppercase; opacity: .9; }}
    .kpi .v {{ font-size: 20px; font-weight: 700; margin-top: 2px; }}
        .section {{ margin-top: 12px; border: 1px solid #cfd9e5; border-radius: 14px; padding: 12px; background: #f7f9fc; page-break-inside: auto; break-inside: auto; }}
    .section h2 {{ margin: 0 0 6px 0; font-size: 18px; color: #0b3c5d; }}
    .two {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
    .chart {{ border: 1px solid #dbe4ee; border-radius: 12px; padding: 8px; background: #fff; }}
    .chart h3 {{ margin: 0 0 6px 0; font-size: 14px; }}
    .chart-interactive .plotly-graph-div {{ width: 100% !important; height: 420px !important; }}
    .chart-static {{ display: none; width: 100%; height: auto; }}
        .chart, .kpi, .chip {{ page-break-inside: avoid; break-inside: avoid; }}
    .data-table {{ width: 100%; border-collapse: collapse; font-size: 10px; table-layout: fixed; }}
    .data-table th, .data-table td {{ border-bottom: 1px solid #d9e2ec; padding: 4px; text-align: left; vertical-align: top; word-wrap: break-word; }}
        .data-table tr {{ page-break-inside: avoid; break-inside: avoid; }}
    .data-table th {{ background: #edf3f9; font-weight: 700; }}
    .chip {{ display: inline-block; padding: 2px 10px; border-radius: 999px; border: 1px solid #f8b58a; background: #fff1e8; color: #7a2f0b; font-size: 10px; margin: 0 6px 6px 0; }}
    .metric-row {{ margin-top: 10px; }}
    .metric-card {{ display: inline-block; min-width: 240px; border: 1px solid #d8c4f2; border-radius: 12px; background: linear-gradient(135deg, #fff1e8, #f5ebff); padding: 8px 12px; }}
    .metric-k {{ font-size: 10px; color: #5b4c6f; text-transform: uppercase; }}
    .metric-v {{ font-size: 20px; font-weight: 700; color: #2f1f45; margin-top: 2px; }}
    .muted {{ color: #5c6b7a; font-size: 12px; }}
        @media print {{
            .top-nav {{ display: none !important; }}
            .two {{ display: block; }}
            .two > div {{ margin-bottom: 10px; }}
            .chart-interactive {{ display: none !important; }}
            .chart-static {{ display: block !important; max-height: 105mm; object-fit: contain; }}
        }}
    .page-break {{ page-break-before: always; break-before: page; }}
  </style>
</head>
<body>
  <div class="wrap">
        <nav class="top-nav">
            <a class="back-link" href="/analysis_outputs/Report_Navigation.html">&larr; Back to Report Navigation</a>
        </nav>
    <section class="hero">
      <h1>Reach Report: Genre and Genre x Emotion by Language</h1>
      <p>Single HTML report with independent language-level adaptive filters (8 -> 5 -> 4).</p>
      <div class="grid">
                <div class="kpi"><div class="k">Languages Included</div><div class="v">{format_human_number(len(language_sections))}</div></div>
                <div class="kpi"><div class="k">Total Labeled Rows</div><div class="v">{format_human_number(total_labeled_rows)}</div></div>
                <div class="kpi"><div class="k">Rows After Filters</div><div class="v">{format_human_number(total_filtered_rows)}</div></div>
                <div class="kpi"><div class="k">Kept Genre x Emotion Pairs</div><div class="v">{format_human_number(total_kept_combos)}</div></div>
      </div>
    </section>

    <section class="section">
      <h2>Language Coverage and Thresholds</h2>
      <span class="chip">Languages analyzed: {', '.join(s['language'].upper() for s in language_sections)}</span>
      <span class="chip">Threshold by language: {threshold_overview}</span>
            <span class="chip">Overall labeled date range: {overall_labeled_date_range}</span>
      <span class="chip">Languages skipped: {skipped_text}</span>
      <p class="muted">Each language is processed independently. Lower thresholds (5 then 4) apply only to that language when 8 is too sparse.</p>
    </section>

    {sections_html}
  </div>
</body>
</html>
"""

    HTML_PATH.write_text(html, encoding='utf-8')

    # Keep PDF generation best-effort so HTML delivery always succeeds.
    try:
        HTML(string=html).write_pdf(str(PDF_PATH))
    except Exception as exc:
        print('PDF generation skipped:', exc)

    language_html_files = []
    language_pdf_files = []
    for section in language_sections:
        slug = safe_token(section['language'])
        lang_html_path = LANGUAGE_REPORTS / f'Reach_Genre_Emotion_Report_8plus_{slug}.html'
        lang_pdf_path = LANGUAGE_REPORTS / f'IG_Reach_Report_Language_{slug.upper()}.pdf'
        lang_html = build_single_language_html(section)
        lang_html_path.write_text(lang_html, encoding='utf-8')
        language_html_files.append(lang_html_path)

        try:
            HTML(string=lang_html).write_pdf(str(lang_pdf_path))
            language_pdf_files.append(lang_pdf_path)
        except Exception as exc:
            print(f'PDF generation skipped for {section["language"]}:', exc)

    print('Generated HTML:', HTML_PATH)
    print('Generated PDF:', PDF_PATH)
    print('Languages included:', ', '.join(s['language'] for s in language_sections))
    print('Thresholds:', threshold_overview)
    print('Generated language HTML files:', ', '.join(str(p) for p in language_html_files))
    if language_pdf_files:
        print('Generated language PDF files:', ', '.join(str(p) for p in language_pdf_files))


if __name__ == '__main__':
    main()

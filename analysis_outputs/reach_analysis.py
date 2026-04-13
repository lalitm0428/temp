import pandas as pd
import numpy as np
from pathlib import Path

SRC = Path('/Users/apple/temp/analysis_outputs/Updated-Genre-Data/Instagram_Genre_Emotion_Reach_Analysis.csv')
OUT = Path('/Users/apple/temp/analysis_outputs')
OUT.mkdir(exist_ok=True)

df = pd.read_csv(SRC, low_memory=False)

if 'Genre.1' not in df.columns and 'genre' in df.columns:
    df['Genre.1'] = df['genre']
if 'Emotions.1' not in df.columns and 'emotion' in df.columns:
    df['Emotions.1'] = df['emotion']
if 'media_type' not in df.columns:
    df['media_type'] = 'post'
if 'caption' not in df.columns:
    df['caption'] = np.nan
if 'permalink' not in df.columns and 'permalink_url' in df.columns:
    df['permalink'] = df['permalink_url']

for c in ['reach', 'views', 'likes', 'comments', 'shares', 'saved', 'total_interactions']:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors='coerce')

for c in ['Genre.1', 'Emotions.1', 'caption', 'permalink', 'post_created_date', 'media_type']:
    if c in df.columns:
        df[c] = df[c].astype(str).str.strip()
        df[c] = df[c].replace({'nan': np.nan, 'None': np.nan, '': np.nan})

reach_df = df[df['reach'].notna()].copy()
label_df = reach_df[reach_df['Genre.1'].notna() & reach_df['Emotions.1'].notna()].copy()

overall_median = float(reach_df['reach'].median())
label_median = float(label_df['reach'].median())

genre_stats = (
    label_df.groupby('Genre.1')
    .agg(
        posts=('reach', 'size'),
        median_reach=('reach', 'median'),
        mean_reach=('reach', 'mean'),
        p75_reach=('reach', lambda s: s.quantile(0.75)),
        max_reach=('reach', 'max'),
    )
    .reset_index()
)
genre_stats['lift_vs_label_median_pct'] = (genre_stats['median_reach'] / label_median - 1) * 100
genre_stats = genre_stats.sort_values('median_reach', ascending=False)

genre_hit_rate = (
    label_df.assign(above_median=(label_df['reach'] >= label_median))
    .groupby('Genre.1')
    .agg(posts=('reach', 'size'), pct_above_median=('above_median', 'mean'))
    .reset_index()
)
genre_hit_rate['pct_above_median'] = genre_hit_rate['pct_above_median'] * 100
genre_hit_rate = genre_hit_rate.sort_values('pct_above_median', ascending=False)

ge_stats = (
    label_df.groupby(['Genre.1', 'Emotions.1'])
    .agg(
        posts=('reach', 'size'),
        median_reach=('reach', 'median'),
        mean_reach=('reach', 'mean'),
        p75_reach=('reach', lambda s: s.quantile(0.75)),
        max_reach=('reach', 'max'),
    )
    .reset_index()
)
ge_stats['lift_vs_label_median_pct'] = (ge_stats['median_reach'] / label_median - 1) * 100
ge_stats_posts3 = ge_stats[ge_stats['posts'] >= 3].sort_values(['median_reach', 'posts'], ascending=[False, False])

post_cols = [
    'post_created_date', 'reach', 'Genre.1', 'Emotions.1', 'caption', 'permalink',
    'likes', 'comments', 'shares', 'saved', 'total_interactions'
]
for c in post_cols:
    if c not in label_df.columns:
        label_df[c] = np.nan

posts = label_df[post_cols].copy()
posts['caption_short'] = posts['caption'].astype(str).map(lambda x: ' '.join(x.split())[:140])
top_posts = posts.sort_values('reach', ascending=False).head(30)
bottom_posts = posts.sort_values('reach', ascending=True).head(30)

combo = ge_stats_posts3.copy()
if len(combo):
    best_emotion_by_genre = (
        combo.sort_values(['Genre.1', 'median_reach'], ascending=[True, False])
        .groupby('Genre.1')
        .head(1)
    )
    worst_emotion_by_genre = (
        combo.sort_values(['Genre.1', 'median_reach'], ascending=[True, True])
        .groupby('Genre.1')
        .head(1)
    )
else:
    best_emotion_by_genre = pd.DataFrame(columns=combo.columns)
    worst_emotion_by_genre = pd.DataFrame(columns=combo.columns)

# Save artifacts
summary = pd.DataFrame([
    {
        'rows_total': len(df),
        'rows_with_reach': len(reach_df),
        'rows_labeled_reach': len(label_df),
        'overall_median_reach': overall_median,
        'labeled_median_reach': label_median,
    }
])
summary.to_csv(OUT / 'summary_metrics.csv', index=False)
genre_stats.to_csv(OUT / 'genre_stats.csv', index=False)
genre_hit_rate.to_csv(OUT / 'genre_hit_rate.csv', index=False)
ge_stats.to_csv(OUT / 'genre_emotion_stats_all.csv', index=False)
ge_stats_posts3.to_csv(OUT / 'genre_emotion_stats_posts3.csv', index=False)
best_emotion_by_genre.to_csv(OUT / 'best_emotion_by_genre_posts3.csv', index=False)
worst_emotion_by_genre.to_csv(OUT / 'worst_emotion_by_genre_posts3.csv', index=False)
top_posts.to_csv(OUT / 'top_posts_labeled.csv', index=False)
bottom_posts.to_csv(OUT / 'bottom_posts_labeled.csv', index=False)

print('rows_total=', len(df))
print('rows_with_reach=', len(reach_df))
print('rows_labeled_reach=', len(label_df))
print('overall_median_reach=', round(overall_median, 2))
print('labeled_median_reach=', round(label_median, 2))
print('top_genres=', genre_stats[['Genre.1', 'posts', 'median_reach']].head(8).to_dict('records'))
print('top_genre_emotion=', ge_stats_posts3[['Genre.1', 'Emotions.1', 'posts', 'median_reach']].head(8).to_dict('records'))
print('bottom_genre_emotion=', ge_stats_posts3[['Genre.1', 'Emotions.1', 'posts', 'median_reach']].tail(8).to_dict('records'))
print('wrote=', OUT)

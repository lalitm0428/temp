import re
from pathlib import Path

import numpy as np
import pandas as pd

SRC = Path('/Users/apple/temp/analysis_outputs/Updated-Genre-Data/Instagram_Genre_Emotion_Reach_Analysis.csv')

df = pd.read_csv(SRC, low_memory=False)

if 'Genre.1' not in df.columns and 'genre' in df.columns:
    df['Genre.1'] = df['genre']
if 'Emotions.1' not in df.columns and 'emotion' in df.columns:
    df['Emotions.1'] = df['emotion']
if 'caption' not in df.columns:
    df['caption'] = np.nan
if 'permalink' not in df.columns and 'permalink_url' in df.columns:
    df['permalink'] = df['permalink_url']
if 'media_type' not in df.columns:
    df['media_type'] = 'post'

for c in ['reach', 'likes', 'comments', 'shares', 'saved', 'total_interactions']:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors='coerce')

for c in ['Genre.1', 'Emotions.1', 'caption', 'permalink', 'post_created_date', 'media_type']:
    if c in df.columns:
        df[c] = df[c].astype(str).str.strip()
        df[c] = df[c].replace({'nan': np.nan, 'None': np.nan, '': np.nan})

reach_df = df[df['reach'].notna()].copy()
label_df = reach_df[reach_df['Genre.1'].notna() & reach_df['Emotions.1'].notna()].copy()
label_df['post_date'] = pd.to_datetime(label_df['post_created_date'], errors='coerce')

date_min = label_df['post_date'].min()
date_max = label_df['post_date'].max()
print('Labeled date range:', date_min.date() if pd.notna(date_min) else 'NA', 'to', date_max.date() if pd.notna(date_max) else 'NA')
print('Labeled rows:', len(label_df))
print('Median reach:', label_df['reach'].median())

media = (
    label_df.groupby('media_type')
    .agg(posts=('reach', 'size'), median_reach=('reach', 'median'), mean_reach=('reach', 'mean'))
    .sort_values('median_reach', ascending=False)
)
print('\nMedia type performance')
print(media.to_string())

print('\nTop 12 posts by reach')
for _, r in label_df.sort_values('reach', ascending=False).head(12).iterrows():
    cap = ' '.join(str(r['caption']).split())[:95]
    print(f"{int(r['reach'])} | {r['Genre.1']} | {r['Emotions.1']} | {r['post_created_date']} | {cap} | {r['permalink']}")

print('\nBottom 12 posts by reach')
for _, r in label_df.sort_values('reach', ascending=True).head(12).iterrows():
    cap = ' '.join(str(r['caption']).split())[:95]
    print(f"{int(r['reach'])} | {r['Genre.1']} | {r['Emotions.1']} | {r['post_created_date']} | {cap} | {r['permalink']}")

# Hashtag profile: top quartile vs bottom quartile reach
q75 = label_df['reach'].quantile(0.75)
q25 = label_df['reach'].quantile(0.25)

def hashtag_counts(series):
    counts = {}
    for txt in series.dropna():
        tags = re.findall(r'#([A-Za-z0-9_]+)', str(txt))
        for t in tags:
            k = t.lower()
            counts[k] = counts.get(k, 0) + 1
    return pd.Series(counts).sort_values(ascending=False)

high = label_df[label_df['reach'] >= q75]
low = label_df[label_df['reach'] <= q25]

high_tags = hashtag_counts(high['caption']).head(20)
low_tags = hashtag_counts(low['caption']).head(20)

print('\nTop hashtags in top quartile reach posts')
print(high_tags.to_string())

print('\nTop hashtags in bottom quartile reach posts')
print(low_tags.to_string())

# Save compact outputs
high[['post_created_date', 'reach', 'Genre.1', 'Emotions.1', 'caption', 'permalink']].to_csv('/Users/apple/temp/analysis_outputs/high_quartile_posts.csv', index=False)
low[['post_created_date', 'reach', 'Genre.1', 'Emotions.1', 'caption', 'permalink']].to_csv('/Users/apple/temp/analysis_outputs/low_quartile_posts.csv', index=False)

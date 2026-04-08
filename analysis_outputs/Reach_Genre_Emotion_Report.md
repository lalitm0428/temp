# Reach Performance Report: Genre and Genre x Emotion

Date: 7 Apr 2026  
Source: DH Social Media Metrics IG Base Data (1).csv

## 1) Executive Summary

This analysis was done on median reach (not average) to identify what is consistently working.

Key findings:

- Total rows in file: 18,127
- Rows with reach available: 2,233
- Rows with both genre and emotion labels plus reach: 729
- Labelled data date range: 6 Mar 2026 to 6 Apr 2026
- Median reach on labelled posts (benchmark): 819

What is working:

- Entertainment is the strongest scaled genre (155 posts, median reach 1,556; +90% vs benchmark).
- Sports is also strong at scale (86 posts, median reach 1,104; +35%).
- Off-beat is slightly above benchmark overall (95 posts, median reach 869; +6%), but highly dependent on emotion.
- Best stable Genre x Emotion combinations (minimum 5 posts) are:
  - Off-beat x Shock -VE (21 posts, median 2,659)
  - Entertainment x Controversy (45 posts, median 2,552)
  - Entertainment x Happiness (11 posts, median 2,335)
  - Sports x Controversy (11 posts, median 2,017)
  - Current-Affairs x Fear/Concern (20 posts, median 1,755)

What is not working:

- Politics, Business, Crime, Lifestyle, and International Politics are structurally weak on median reach in this period.
- Weak Genre x Emotion combinations (minimum 5 posts) include:
  - Off-beat x Controversy (5 posts, median 24)
  - Current-Affairs x Wow! Amazing! (8 posts, median 25.5)
  - Current-Affairs x Sadness (11 posts, median 26)
  - Business x Shock -VE (14 posts, median 27.5)
  - Sports x Sadness (6 posts, median 28)

## 2) Method Used

- Primary KPI: reach
- Decision metric: median reach
- Why median: protects against extreme outliers (a few viral posts are present)
- Stability filter for Genre x Emotion recommendations: minimum 5 posts
- Supporting metrics reviewed: post count, hit-rate above median, top and bottom post examples

## 3) Genre Performance (Median Reach)

Benchmark: 819 median reach on labelled posts.

| Genre | Posts | Median Reach | Lift vs Benchmark |
|---|---:|---:|---:|
| Entertainment | 155 | 1,556 | +90.0% |
| Sports | 86 | 1,104 | +34.8% |
| Off-beat | 95 | 869 | +6.1% |
| Current-Affairs | 161 | 750 | -8.4% |
| Politics | 74 | 52 | -93.7% |
| Crime | 54 | 44.5 | -94.6% |
| Lifestyle | 22 | 40.5 | -95.1% |
| Business | 31 | 35 | -95.7% |
| International Politics | 28 | 45.5 | -94.4% |

Hit-rate above benchmark median (819):

- Sports: 70.9%
- Entertainment: 65.8%
- Off-beat: 52.6%
- Current-Affairs: 49.7%
- Business: 19.4%
- Politics: 27.0%

Interpretation:

- Entertainment and Sports should be the two core scale pillars.
- Off-beat should be retained with tighter emotion control.
- Current-Affairs is mixed and needs emotion-level optimization.
- Politics/Business/Crime/Lifestyle/Int-Politics require format and narrative redesign before scaling volume.

## 4) Genre x Emotion: What to Scale

Stable winners (minimum 5 posts):

| Genre x Emotion | Posts | Median Reach | Notes |
|---|---:|---:|---|
| Off-beat x Shock -VE | 21 | 2,659 | Highest repeatable median; strong attention pull. |
| Entertainment x Controversy | 45 | 2,552 | Best scaled winner with very high repeatability. |
| Entertainment x Happiness | 11 | 2,335 | Positive celebrity/pop culture works. |
| Sports x Controversy | 11 | 2,017 | Debate-driven sports stories perform strongly. |
| Current-Affairs x Fear/Concern | 20 | 1,755 | Risk/alert framing drives reach in current affairs. |
| Current-Affairs x Controversy | 13 | 1,545 | Polarized topics outperform neutral framing. |
| Entertainment x Curiosity | 20 | 1,514 | Curiosity hooks are consistently strong. |

## 5) Genre x Emotion: What to Reduce or Rework

Stable underperformers (minimum 5 posts):

| Genre x Emotion | Posts | Median Reach | Action |
|---|---:|---:|---|
| Off-beat x Controversy | 5 | 24 | Avoid in current format; switch to Shock/Fear framing. |
| Current-Affairs x Wow! Amazing! | 8 | 25.5 | Low match with audience intent; deprioritize. |
| Current-Affairs x Sadness | 11 | 26 | Reframe to impact/urgency or solution angle. |
| Business x Shock -VE | 14 | 27.5 | Current execution not converting; test utility-led hooks. |
| Sports x Sadness | 6 | 28 | Replace with rivalry, stakes, or celebration frame. |
| Politics x Shock -VE | 14 | 40 | Very weak median; only publish when backed by strong story value. |

## 6) Post-Level Signals (From Best and Worst Reach Posts)

Top-performing post patterns:

- Celebrity relationship/family controversy (Entertainment x Controversy) dominates top reach.
- High-stakes taboo or socially polarizing off-beat stories perform strongly.
- Sports wins when narrative is high-stakes or emotionally charged (titles, controversy, fandom moments).
- Current-Affairs performs when linked to immediate risk, concern, or practical impact.

Lowest-performing post patterns:

- Several posts with reach 0 are present, including reels; these likely indicate distribution issues, publishing timing mismatch, or account-level delivery constraints.
- Generic informational posts without urgency or conflict tend to underperform.
- Positive but low-tension framings in hard-news genres underperform.

## 7) Content Team Playbook (Actionable)

1. Keep 60-70% of volume in proven lanes:
   - Entertainment x Controversy/Curiosity/Happiness
   - Sports x Controversy/Happiness
   - Off-beat x Shock -VE

2. Rebuild Current-Affairs strategy by emotion:
   - Scale Fear/Concern and Controversy
   - Reduce Surprise +VE, Sadness, Wow! Amazing!

3. Put weak lanes in test mode only (10-15% volume):
   - Business, Politics, Crime, Lifestyle, Int-Politics
   - Each post must have explicit hook tests in first line

4. Run a weekly median dashboard, not mean dashboard:
   - Median reach by Genre and Genre x Emotion
   - Hit-rate above benchmark median
   - Outlier tracker for viral spikes (for learning, not planning baseline)

5. Investigate zero-reach cases operationally:
   - Posting time slots
   - Account health and distribution
   - Reel metadata consistency

## 8) Suggested Next 2-Week Publishing Mix

- 35% Entertainment (majority Controversy + Curiosity)
- 25% Sports (Controversy + Happiness + Surprise +VE)
- 20% Off-beat (mostly Shock -VE)
- 15% Current-Affairs (Fear/Concern + Controversy only)
- 5% Experimental (Business/Politics/Lifestyle/Crime in strict A/B tests)

## 9) Files Generated

- analysis_outputs/summary_metrics.csv
- analysis_outputs/genre_stats.csv
- analysis_outputs/genre_hit_rate.csv
- analysis_outputs/genre_emotion_stats_posts3.csv
- analysis_outputs/top_posts_labeled.csv
- analysis_outputs/bottom_posts_labeled.csv
- analysis_outputs/high_quartile_posts.csv
- analysis_outputs/low_quartile_posts.csv

These files can be directly used for slides and weekly review decks.

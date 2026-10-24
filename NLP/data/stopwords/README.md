# Stopword lists

Used by co-word analysis (`NLP.text_utils.stopwords`). Snowball lists are
preferred; stopwords-iso fills in languages Snowball does not cover.

| Files | Source | License |
|---|---|---|
| `snowball/*.txt` (17 languages) | Snowball project, `algorithms/<language>/stop.txt` at commit [`dc14fb462784`](https://github.com/snowballstem/snowball-website/tree/dc14fb462784e5bdf90f3210022b0f91d3881ffd/algorithms) | BSD-3-Clause ("all the software given out on this Snowball site", https://snowballstem.org/license.html). Copyright (c) 2001 Dr Martin Porter, (c) 2002 Richard Boulton. |
| `stopwords-iso.json` (58 languages) | [stopwords-iso](https://github.com/stopwords-iso/stopwords-iso) at commit [`6e8e9a2d1c01`](https://github.com/stopwords-iso/stopwords-iso/tree/6e8e9a2d1c019ad2a885bcbe157628dea624dfb6) | MIT, see `stopwords-iso.LICENSE`. The compilation aggregates many public lists; they are broader than Snowball's and can include content words, so the UI labels them "extended". |

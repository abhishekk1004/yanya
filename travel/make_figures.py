import os
import sys

import django
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")
django.setup()

from travel.evaluation import evaluate, synth_dataset  

CRIMSON, BLUE, MUTED = "#dc143c", "#1e5bd6", "#9aa6d4"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT, exist_ok=True)

data = synth_dataset(n_users=120, seed=42)
m5 = evaluate(data, k=5, seed=42)



fig, ax = plt.subplots(figsize=(6.5, 4))
labels = ["RMSE", "MAE"]
model = [m5.rmse, m5.mae]
base = [m5.baseline_rmse, m5.baseline_mae]
x = np.arange(len(labels)); w = 0.35
ax.bar(x - w / 2, model, w, label="Content model", color=CRIMSON)
ax.bar(x + w / 2, base, w, label="Mean baseline", color=MUTED)
for i, (mv, bv) in enumerate(zip(model, base)):
    ax.text(i - w / 2, mv + 0.02, f"{mv:.3f}", ha="center", fontweight="bold")
    ax.text(i + w / 2, bv + 0.02, f"{bv:.3f}", ha="center")
ax.set_ylabel("Error (lower is better)"); ax.set_xticks(x); ax.set_xticklabels(labels)
ax.set_title("Rating prediction error — model vs baseline", fontweight="bold")
ax.legend(); ax.grid(axis="y", alpha=0.3)
plt.tight_layout(); plt.savefig(os.path.join(OUT, "fig_error_metrics.png"), dpi=150)
plt.close()



ks = list(range(1, 11))
model_r, rand_r = [], []
for k in ks:
    mk = evaluate(data, k=k, seed=42)
    model_r.append(mk.recall_at_k); rand_r.append(mk.random_recall_at_k)
fig, ax = plt.subplots(figsize=(6.5, 4))
ax.plot(ks, model_r, "-o", color=CRIMSON, label="Content model")
ax.plot(ks, rand_r, "--o", color=MUTED, label="Random baseline")
ax.set_xlabel("K"); ax.set_ylabel("Recall@K (higher is better)")
ax.set_title("Recall@K — model vs random baseline", fontweight="bold")
ax.legend(); ax.grid(alpha=0.3)
plt.tight_layout(); plt.savefig(os.path.join(OUT, "fig_recall_at_k.png"), dpi=150)
plt.close()


#behaviour-blend weight alpha = n/(n+K) ---
K = 8.0
n = np.arange(0, 41)
alpha = n / (n + K)
fig, ax = plt.subplots(figsize=(6.5, 4))
ax.plot(n, alpha, color=BLUE, linewidth=2)
ax.axhline(0.5, color=MUTED, ls="--", lw=1)
ax.axvline(K, color=CRIMSON, ls="--", lw=1, label=f"n = K = {int(K)} → α = 0.5")
ax.set_xlabel("Number of signalled interactions (n)")
ax.set_ylabel("Behavioural weight  α = n/(n+K)")
ax.set_title("Cold-start blend: quiz taste → behavioural taste", fontweight="bold")
ax.legend(); ax.grid(alpha=0.3); ax.set_ylim(0, 1)
plt.tight_layout(); plt.savefig(os.path.join(OUT, "fig_blend_alpha.png"), dpi=150)
plt.close()


#  Figure: user-item rating matrix (CF input)
from travel.evaluation import _predict, _split  # noqa: E402
from travel import fuzzy  # noqa: E402

rng = np.random.default_rng(7)
n_u, n_i = 8, 8
R = np.full((n_u, n_i), np.nan)
tastes = rng.integers(0, 2, size=(n_u, 2))  
for u in range(n_u):
    for i in rng.choice(n_i, size=5, replace=False):
        base = 4.3 if (i % 2) == tastes[u, 0] else 2.2
        R[u, i] = float(np.clip(round(base + rng.normal(0, 0.5)), 1, 5))

fig, ax = plt.subplots(figsize=(6.2, 4.6))
im = ax.imshow(np.ma.masked_invalid(R), cmap="RdYlGn", vmin=1, vmax=5, aspect="auto")
for u in range(n_u):
    for i in range(n_i):
        if not np.isnan(R[u, i]):
            ax.text(i, u, int(R[u, i]), ha="center", va="center", fontsize=9)
ax.set_xticks(range(n_i)); ax.set_xticklabels([f"P{i+1}" for i in range(n_i)])
ax.set_yticks(range(n_u)); ax.set_yticklabels([f"U{u+1}" for u in range(n_u)])
ax.set_xlabel("Places"); ax.set_ylabel("Users")
ax.set_title("User–item rating matrix (blank = not rated)", fontweight="bold")
fig.colorbar(im, ax=ax, label="rating (1–5)")
plt.tight_layout(); plt.savefig(os.path.join(OUT, "fig_rating_matrix.png"), dpi=150)
plt.close()


# Figure: user-user cosine similarity matrix (CF)
def cos_sim(a, b):
    mask = ~np.isnan(a) & ~np.isnan(b)
    if mask.sum() == 0:
        return 0.0
    x, y = a[mask], b[mask]
    d = np.linalg.norm(x) * np.linalg.norm(y)
    return float(x @ y / d) if d else 0.0

S = np.array([[cos_sim(R[a], R[b]) for b in range(n_u)] for a in range(n_u)])
fig, ax = plt.subplots(figsize=(5.6, 4.8))
im = ax.imshow(S, cmap="Blues", vmin=0, vmax=1)
for a in range(n_u):
    for b in range(n_u):
        ax.text(b, a, f"{S[a,b]:.2f}", ha="center", va="center", fontsize=7,
                color="white" if S[a, b] > 0.6 else "black")
ax.set_xticks(range(n_u)); ax.set_xticklabels([f"U{u+1}" for u in range(n_u)])
ax.set_yticks(range(n_u)); ax.set_yticklabels([f"U{u+1}" for u in range(n_u)])
ax.set_title("User–user cosine similarity (CF neighbours)", fontweight="bold")
fig.colorbar(im, ax=ax, label="cosine similarity")
plt.tight_layout(); plt.savefig(os.path.join(OUT, "fig_user_similarity.png"), dpi=150)
plt.close()


#  Figure: fuzzy membership functions 
fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
r = np.linspace(0, 2, 300)
axes[0].plot(r, fuzzy.aff_cheap(r), label="cheap", color="#2e7d32")
axes[0].plot(r, fuzzy.aff_moderate(r), label="moderate", color="#f9a825")
axes[0].plot(r, fuzzy.aff_expensive(r), label="expensive", color=CRIMSON)
axes[0].axvline(1.0, ls="--", color=MUTED, lw=1)
axes[0].set_title("Affordability  (price / budget)", fontweight="bold")
axes[0].set_xlabel("ratio"); axes[0].set_ylabel("membership"); axes[0].legend(fontsize=8)
s = np.linspace(1, 5, 300)
axes[1].plot(s, fuzzy.rate_low(s), label="low", color=CRIMSON)
axes[1].plot(s, fuzzy.rate_medium(s), label="medium", color="#f9a825")
axes[1].plot(s, fuzzy.rate_high(s), label="high", color="#2e7d32")
axes[1].set_title("Star rating", fontweight="bold")
axes[1].set_xlabel("stars"); axes[1].legend(fontsize=8)
plt.tight_layout(); plt.savefig(os.path.join(OUT, "fig_fuzzy_membership.png"), dpi=150)
plt.close()


# Figure: fuzzy recommendation surface
budget = 6000.0
prices = np.linspace(1500, 15000, 40)
ratings = np.linspace(1, 5, 40)
Z = np.array([[fuzzy.infer(p, budget, rt) for p in prices] for rt in ratings])
fig, ax = plt.subplots(figsize=(6.4, 4.4))
c = ax.contourf(prices, ratings, Z, levels=12, cmap="viridis")
ax.set_xlabel("Hotel price (NPR/night), budget = 6000"); ax.set_ylabel("Star rating")
ax.set_title("Fuzzy recommendation score surface", fontweight="bold")
fig.colorbar(c, ax=ax, label="score (0–100)")
plt.tight_layout(); plt.savefig(os.path.join(OUT, "fig_fuzzy_surface.png"), dpi=150)
plt.close()


# Figure: Precision@K and Recall@K (retrieval accuracy)
def precision_recall_at_k(data, k, seed=0):
    rng = np.random.default_rng(seed)
    precs, recs = [], []
    place_ids = list(data.places)
    for user_ratings in data.ratings.values():
        if len(user_ratings) < 2:
            continue
        train, test = _split(user_ratings, rng)
        user_mean = float(np.mean([r for _, r in train])) if train else 3.0
        liked = {pid for pid, r in test if r >= 4}
        if not liked:
            continue
        trained = {pid for pid, _ in train}
        cands = [p for p in place_ids if p not in trained]
        ranked = sorted(cands, key=lambda p: _predict(data.places[p].vector, train,
                        data.places, user_mean), reverse=True)[:k]
        hits = len(set(ranked) & liked)
        precs.append(hits / k)
        recs.append(hits / len(liked))
    return float(np.mean(precs)), float(np.mean(recs))

ks = list(range(1, 11))
precisions, recalls = zip(*[precision_recall_at_k(data, k, seed=42) for k in ks])
fig, ax = plt.subplots(figsize=(6.5, 4))
ax.plot(ks, precisions, "-o", color=BLUE, label="Precision@K")
ax.plot(ks, recalls, "-o", color=CRIMSON, label="Recall@K")
ax.set_xlabel("K"); ax.set_ylabel("score"); ax.set_ylim(0, 1)
ax.set_title("Retrieval accuracy — Precision@K and Recall@K", fontweight="bold")
ax.legend(); ax.grid(alpha=0.3)
plt.tight_layout(); plt.savefig(os.path.join(OUT, "fig_precision_recall_k.png"), dpi=150)
plt.close()

print("Wrote figures to", OUT)
print(f"RMSE {m5.rmse:.3f} vs {m5.baseline_rmse:.3f} | "
      f"MAE {m5.mae:.3f} vs {m5.baseline_mae:.3f} | "
      f"Recall@5 {m5.recall_at_k:.3f} vs {m5.random_recall_at_k:.3f}")

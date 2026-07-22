"""Evaluate the content-based recommender with an 80/20 split.

Runs fully offline on synthetic data by default; point it at a real Kaggle
tourism dataset with --places / --ratings. Prints RMSE/MAE (vs a mean-rating
baseline) and Recall@K (vs a random-ranking baseline).

    python manage.py eval_recommender
    python manage.py eval_recommender --places data/places.csv --ratings data/ratings.csv
"""
from django.core.management.base import BaseCommand

from travel.evaluation import evaluate, load_csv, synth_dataset


class Command(BaseCommand):
    help = "Evaluate the recommender (RMSE/MAE + Recall@K vs random baseline)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--places", help="places CSV (Kaggle-style)")
        parser.add_argument("--ratings", help="ratings CSV")
        parser.add_argument("--k", type=int, default=5, help="K for Recall@K")
        parser.add_argument("--users", type=int, default=120, help="synthetic users")
        parser.add_argument("--seed", type=int, default=42)

    def handle(self, *args, **opts) -> None:
        if opts["places"] and opts["ratings"]:
            data = load_csv(opts["places"], opts["ratings"])
            source = f"{opts['places']} + {opts['ratings']}"
        else:
            data = synth_dataset(n_users=opts["users"], seed=opts["seed"])
            source = f"synthetic ({opts['users']} users)"

        m = evaluate(data, k=opts["k"], seed=opts["seed"])
        better_rmse = m.rmse < m.baseline_rmse
        better_recall = m.recall_at_k > m.random_recall_at_k

        out = self.stdout
        total = m.n_train + m.n_test
        pct_train = (100 * m.n_train / total) if total else 0
        pct_test = (100 * m.n_test / total) if total else 0
        out.write(self.style.MIGRATE_HEADING(f"\nRecommender evaluation — {source}"))
        out.write(f"  users evaluated     : {m.n_users}")
        out.write(f"  ratings total       : {total}")
        out.write(f"  train / test split  : {m.n_train} ({pct_train:.0f}%) / "
                  f"{m.n_test} ({pct_test:.0f}%)")
        out.write(f"  RMSE (model)        : {m.rmse:.3f}")
        out.write(f"  RMSE (mean baseline): {m.baseline_rmse:.3f}")
        out.write(f"  MAE  (model)        : {m.mae:.3f}")
        out.write(f"  MAE  (mean baseline): {m.baseline_mae:.3f}")
        out.write(f"  Recall@{m.k} (model)   : {m.recall_at_k:.3f}")
        out.write(f"  Recall@{m.k} (random)  : {m.random_recall_at_k:.3f}")
        verdict = "beats" if (better_rmse and better_recall) else "does not fully beat"
        style = self.style.SUCCESS if (better_rmse and better_recall) else self.style.WARNING
        out.write(style(f"  → model {verdict} the baseline.\n"))

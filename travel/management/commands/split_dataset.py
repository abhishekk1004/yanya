"""Write an explicit 80/20 train/test split of a ratings CSV.

Produces ``ratings_train.csv`` and ``ratings_test.csv`` next to the input so an
assignment can show the two files directly. The split is stratified per user
(each user contributes ~80% of their ratings to train, ~20% to test), which is
exactly what the evaluator does internally.

    python manage.py split_dataset data/ratings.csv --test-frac 0.2
"""
import csv
import os
from collections import defaultdict

import numpy as np
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Split a ratings CSV into 80% train / 20% test files (per user)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("ratings", help="path to ratings.csv (user_id,place_id,rating)")
        parser.add_argument("--test-frac", type=float, default=0.2)
        parser.add_argument("--seed", type=int, default=42)

    def handle(self, *args, **opts) -> None:
        path = opts["ratings"]
        if not os.path.exists(path):
            raise CommandError(f"No such file: {path}")

        with open(path, newline="") as fh:
            reader = csv.reader(fh)
            header = next(reader)
            rows = list(reader)

        # Group row indices by user (first column) for a per-user split.
        by_user: dict[str, list[int]] = defaultdict(list)
        for i, row in enumerate(rows):
            by_user[row[0]].append(i)

        rng = np.random.default_rng(opts["seed"])
        test_idx: set[int] = set()
        for _, idxs in by_user.items():
            idxs = np.array(idxs)
            rng.shuffle(idxs)
            n_test = max(1, int(round(len(idxs) * opts["test_frac"])))
            test_idx.update(idxs[:n_test].tolist())

        base, ext = os.path.splitext(path)
        train_path, test_path = f"{base}_train{ext}", f"{base}_test{ext}"
        n_train = n_test = 0
        with open(train_path, "w", newline="") as ftr, open(test_path, "w", newline="") as fte:
            wtr, wte = csv.writer(ftr), csv.writer(fte)
            wtr.writerow(header)
            wte.writerow(header)
            for i, row in enumerate(rows):
                if i in test_idx:
                    wte.writerow(row); n_test += 1
                else:
                    wtr.writerow(row); n_train += 1

        total = n_train + n_test
        self.stdout.write(self.style.SUCCESS(
            f"Split {total} ratings → train {n_train} ({100*n_train/total:.0f}%) "
            f"[{train_path}], test {n_test} ({100*n_test/total:.0f}%) [{test_path}]"
        ))

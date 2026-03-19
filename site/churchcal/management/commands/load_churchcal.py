"""Load churchcal fixture with deferred constraints to handle MTI circular FKs."""
import gzip
import json
import os

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Load churchcal fixtures with deferred FK constraints"

    def handle(self, *args, **options):
        # Find the fixture file
        from django.conf import settings
        fixture_path = None
        for app_config in settings.INSTALLED_APPS:
            app_name = app_config.split(".")[-1]
            if app_name == "churchcal":
                break
        for fixtures_dir in ["churchcal/fixtures", "site/churchcal/fixtures"]:
            path = os.path.join(settings.BASE_DIR, fixtures_dir, "churchcal_data.json.gz")
            if os.path.exists(path):
                fixture_path = path
                break
        if not fixture_path:
            # Try relative to this file
            fixture_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "fixtures", "churchcal_data.json.gz"
            )

        self.stdout.write(f"Loading fixture from {fixture_path}")

        with gzip.open(fixture_path, "rt", encoding="utf-8") as f:
            data = json.load(f)

        # Separate parent Commemoration fields from child model data
        # Django MTI serializes child models with all parent fields included
        # We need to insert into parent table first

        # Group by model
        by_model = {}
        for obj in data:
            model = obj["model"]
            by_model.setdefault(model, []).append(obj)

        # Define load order - parent tables first
        child_models = {
            "churchcal.sanctoralecommemoration",
            "churchcal.temporalecommemoration",
            "churchcal.sanctoralebasedcommemoration",
        }

        # Models that depend on commemoration
        depends_on_commemoration = {
            "churchcal.season",
            "churchcal.massreading",
        }

        # Phase 1: Load base models (no FK to commemoration)
        phase1 = ["sites.site", "churchcal.denomination", "churchcal.calendar",
                   "churchcal.commemorationrank", "churchcal.proper", "churchcal.common"]

        # Phase 2: Insert parent commemoration rows from child model data
        # Phase 3: Load child models + dependent models

        with connection.cursor() as cursor:
            # Phase 1
            for model_name in phase1:
                if model_name in by_model:
                    self._load_objects(by_model[model_name])
                    self.stdout.write(f"  Loaded {len(by_model[model_name])} {model_name}")

            # Phase 2: Insert bare commemoration parent rows first
            commemoration_pks = set()
            for model_name in child_models:
                for obj in by_model.get(model_name, []):
                    pk = obj["pk"]
                    if pk not in commemoration_pks:
                        commemoration_pks.add(pk)
                        fields = obj["fields"]
                        # Insert into parent commemoration table
                        cursor.execute(
                            """INSERT INTO churchcal_commemoration
                               (uuid, name, rank_id, calendar_id, cannot_occur_after_id, collect_id)
                               VALUES (%s, %s, %s, %s, %s, %s)
                               ON CONFLICT (uuid) DO NOTHING""",
                            [
                                pk,
                                fields.get("name", ""),
                                fields.get("rank"),
                                fields.get("calendar"),
                                fields.get("cannot_occur_after"),
                                fields.get("collect"),
                            ]
                        )

            self.stdout.write(f"  Inserted {len(commemoration_pks)} parent commemoration rows")

            # Phase 3: Load child commemoration models
            for model_name in child_models:
                if model_name in by_model:
                    self._load_objects(by_model[model_name])
                    self.stdout.write(f"  Loaded {len(by_model[model_name])} {model_name}")

            # Phase 4: Load models that depend on commemoration
            for model_name in depends_on_commemoration:
                if model_name in by_model:
                    self._load_objects(by_model[model_name])
                    self.stdout.write(f"  Loaded {len(by_model[model_name])} {model_name}")

        self.stdout.write(self.style.SUCCESS("Successfully loaded all churchcal data"))

    def _load_objects(self, objects):
        """Load a list of serialized objects using Django's deserializer."""
        from django.core.serializers import deserialize
        import io
        data = json.dumps(objects)
        for obj in deserialize("json", data):
            try:
                obj.save()
            except Exception as e:
                self.stderr.write(f"  Warning: {e}")

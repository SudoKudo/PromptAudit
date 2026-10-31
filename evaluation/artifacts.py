"""Read saved predictions and responses without loading a whole study into RAM."""

from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile


GROUP_FIELDS = ("dataset", "model_id", "model", "run_seed", "protocol", "parser_mode")


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _hash(value):
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _known_model_identity(info):
    if not isinstance(info, dict) or info.get("metadata_error"):
        return False
    if any(info.get(key) for key in ("digest", "resolved_revision", "cache_identity")):
        return True
    return any(_known_model_identity(value) for value in info.values() if isinstance(value, dict))


class _Rows(Sequence):
    """Each iteration opens a cursor; only the current row is decoded."""

    def __init__(self, reader, where, arguments):
        self.reader, self.where, self.arguments = reader, where, arguments

    def __len__(self):
        return self.reader.db.execute("SELECT COUNT(*) FROM predictions WHERE " + self.where,
                                      self.arguments).fetchone()[0]

    def __iter__(self):
        cursor = self.reader.db.execute("SELECT row FROM predictions WHERE " + self.where + " ORDER BY seq",
                                        self.arguments)
        for index, (value,) in enumerate(cursor):
            self.reader._control(index)
            yield json.loads(value)

    def __getitem__(self, index):
        if isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            return [self[position] for position in range(start, stop, step)]
        if index < 0:
            index += len(self)
        if index < 0:
            raise IndexError(index)
        found = self.reader.db.execute("SELECT row FROM predictions WHERE " + self.where
            + " ORDER BY seq LIMIT 1 OFFSET ?", (*self.arguments, index)).fetchone()
        if found is None:
            raise IndexError(index)
        return json.loads(found[0])


class _Conditions(Mapping):
    def __init__(self, reader, group_key, *, protocol=False, source=None):
        self.reader, self.key, self.protocol, self.source = reader, _json(group_key), protocol, source

    @property
    def source_filter(self):
        return (" AND artifact=?", (self.source,)) if self.source is not None else ("", ())

    @property
    def columns(self):
        return ("protocol_key", "protocol") if self.protocol else ("group_key", "condition")

    def __iter__(self):
        parent, child = self.columns
        suffix, arguments = self.source_filter
        query = f"SELECT {child} FROM predictions WHERE {parent}=?{suffix} GROUP BY {child} ORDER BY MIN(seq)"
        for (value,) in self.reader.db.execute(query, (self.key, *arguments)):
            yield value

    def __len__(self):
        parent, child = self.columns
        suffix, arguments = self.source_filter
        return self.reader.db.execute(f"SELECT COUNT(DISTINCT {child}) FROM predictions WHERE {parent}=?{suffix}",
                                      (self.key, *arguments)).fetchone()[0]

    def __getitem__(self, value):
        parent, child = self.columns
        suffix, arguments = self.source_filter
        rows = _Rows(self.reader, f"{parent}=? AND {child}=?{suffix}", (self.key, value, *arguments))
        if not len(rows):
            raise KeyError(value)
        return rows


class _Groups(Mapping):
    def __init__(self, reader, *, protocol=False, source=None):
        self.reader, self.protocol, self.source = reader, protocol, source

    @property
    def source_filter(self):
        return (" WHERE artifact=?", (self.source,)) if self.source is not None else ("", ())

    @property
    def column(self):
        return "protocol_key" if self.protocol else "group_key"

    def __iter__(self):
        suffix, arguments = self.source_filter
        query = f"SELECT {self.column} FROM predictions{suffix} GROUP BY {self.column} ORDER BY MIN(seq)"
        for (value,) in self.reader.db.execute(query, arguments):
            yield tuple(json.loads(value))

    def __len__(self):
        suffix, arguments = self.source_filter
        return self.reader.db.execute(f"SELECT COUNT(DISTINCT {self.column}) FROM predictions{suffix}", arguments).fetchone()[0]

    def __getitem__(self, value):
        conditions = _Conditions(self.reader, value, protocol=self.protocol, source=self.source)
        if not len(conditions):
            raise KeyError(value)
        return conditions


class ArtifactReader:
    """Index one saved Standard run or study in temporary, bounded-cache SQLite."""

    def __init__(self, output, control=None):
        self.sources = [Path(path).resolve() for path in (output if isinstance(output, (list, tuple)) else [output])]
        if not self.sources or len(set(self.sources)) != len(self.sources):
            raise ValueError("Select one or more distinct saved run directories")
        self.output = self.sources[0]
        self.control = control
        self._temporary = tempfile.TemporaryDirectory(prefix="promptaudit-analysis-")
        self.db = sqlite3.connect(Path(self._temporary.name) / "predictions.sqlite3")
        self.db.execute("PRAGMA cache_size=-8192")
        self.db.execute("PRAGMA temp_store=FILE")
        self.db.execute("CREATE TABLE predictions (seq INTEGER PRIMARY KEY, artifact INTEGER, group_key TEXT, condition TEXT, "
                        "protocol_key TEXT, protocol TEXT, row TEXT)")
        self.db.execute("CREATE TABLE generations (id TEXT, artifact INTEGER, offset INTEGER, PRIMARY KEY(id,artifact))")
        self.db.execute("CREATE TABLE response_inputs (artifact INTEGER, id TEXT, checksum TEXT, PRIMARY KEY(artifact,id))")
        self._raw_streams = {}
        self._response_dbs = {}
        self._response_versions = {}
        self._response_hashes_dirty = False
        self._generations_indexed = False
        self._snapshots = {}
        self._input_hashes = {}
        try:
            self.source_manifests, self.source_kinds = [], []
            for self._source_index, self._reading_output in enumerate(self.sources):
                if (self._reading_output / "manifest.json").exists():
                    kind = "study"
                    self.manifest = self._read_json("manifest.json")
                    self._index_study()
                elif (self._reading_output / "records.jsonl").exists():
                    kind = "standard"
                    checkpoint = self._read_json("checkpoint.json") if (self._reading_output / "checkpoint.json").exists() else {}
                    self.manifest = {**checkpoint, "schema_version": 0,
                        "status": checkpoint.get("status", "completed"), "pilot": checkpoint.get("pilot", False),
                        "config": {"analysis": checkpoint.get("analysis", {}),
                                   "generation": checkpoint.get("gen_cfg", {})}}
                    self._index_standard()
                else:
                    raise ValueError("Expected a study manifest or Standard records.jsonl in each run directory")
                self.source_manifests.append(self.manifest)
                self.source_kinds.append(kind)
            if len({bool(manifest.get("pilot", False)) for manifest in self.source_manifests}) > 1:
                raise ValueError("Pilot and full runs must be analyzed separately")
            self.kind = self.source_kinds[0] if len(set(self.source_kinds)) == 1 else "mixed"
            self.manifest = dict(self.source_manifests[0])
            if len(self.sources) > 1:
                self.manifest["inference_performance"] = [row for manifest in self.source_manifests
                                                          for row in manifest.get("inference_performance", [])]
            self.db.execute("CREATE INDEX prediction_groups ON predictions(group_key, condition, seq)")
            self.db.execute("CREATE INDEX protocol_groups ON predictions(protocol_key, protocol, seq)")
            overlapping = self.db.execute(
                "SELECT 1 FROM predictions GROUP BY group_key,condition HAVING COUNT(DISTINCT artifact)>1 LIMIT 1"
            ).fetchone()
            if overlapping:
                raise ValueError("Duplicate predictions: the same configuration and run seed occur in multiple artifacts")
            self.db.commit()
            self.groups = _Groups(self)
            self.protocol_groups = _Groups(self, protocol=True)
        except BaseException:
            self.close()
            raise

    def _control(self, index=0):
        if self.control and index % 1000 == 0:
            self.control()

    def _capture(self, path):
        stat = path.stat()
        self._snapshots[path] = (stat.st_size, stat.st_mtime_ns)

    def _read_json(self, filename):
        path = self._reading_output / filename
        self._capture(path)
        value = path.read_bytes()
        self.input_hashes[self._input_name(filename)] = hashlib.sha256(value).hexdigest()
        return json.loads(value)

    def _lines(self, filename):
        path = self._reading_output / filename
        self._capture(path)
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for index, line in enumerate(stream):
                self._control(index)
                digest.update(line)
                if line.strip():
                    yield json.loads(line)
        self.input_hashes[self._input_name(filename)] = digest.hexdigest()

    def _input_name(self, filename):
        return filename if len(self.sources) == 1 else f"source_{self._source_index + 1}/{filename}"

    def _insert(self, row):
        key = tuple(row[field] for field in GROUP_FIELDS)
        protocol_key = tuple(row[field] for field in GROUP_FIELDS if field != "protocol")
        protocol_key += (row["condition"].rsplit("/", 1)[0],)
        self.db.execute("INSERT INTO predictions(artifact,group_key,condition,protocol_key,protocol,row) VALUES (?,?,?,?,?,?)",
                        (self._source_index, _json(key), row["condition"], _json(protocol_key), row["protocol"], _json(row)))

    def _index_study(self):
        config = self.manifest.get("config", {})
        generation = {key: value for key, value in config.get("generation", {}).items()
                      if key not in {"seed", "experiment_name", "experiment_notes"}}
        settings_hash = _hash({"generation": generation, "models": config.get("models"),
            "resolved": self.manifest.get("resolved_models"), "sources": self.manifest.get("source_hashes")})
        model_settings = {}
        for row in self._lines("predictions.jsonl"):
            row = dict(row)
            row["traceability_available"] = bool(row.get("sample_uid") and row.get("code_sha256"))
            model_id = row.get("model_id")
            if model_id not in model_settings:
                namespace = self.manifest.get("inference_namespaces", {}).get(model_id)
                resolved = self.manifest.get("resolved_models", {}).get(model_id, {})
                model_settings[model_id] = (
                    _hash({"study_settings": settings_hash, "inference_namespace": namespace}),
                    bool(namespace and _known_model_identity(resolved)),
                )
            row["analysis_settings_hash"], row["analysis_identity_available"] = model_settings[model_id]
            self._insert(row)

    def _index_standard(self):
        if self.manifest.get("status") not in {"completed", "generated"}:
            raise ValueError("Analysis requires completed Standard generation; resume the interrupted run first")
        for record in self._lines("records.jsonl"):
            if record.get("is_partial"):
                raise ValueError("Analysis requires completed Standard records; resume the interrupted run first")
            params = record.get("params", {})
            model_id = record.get("model_id") or _hash({"model": record.get("model"),
                                                        "backend": record.get("model_backend")})
            protocol = record.get("output_protocol", record.get("label_protocol", "verdict_first"))
            family = record.get("prompt", "unknown")
            context = {"dataset": record.get("dataset", "unknown"), "model_id": model_id,
                "model": record.get("model", "unknown"), "run_seed": record.get("run_seed", params.get("seed", 42)),
                "protocol": protocol, "parser_mode": record.get("parser_mode", "full"),
                "condition": f"standard/{family}/{protocol}", "comparison": "standard", "family": family,
                "variant": "reference"}
            settings = {key: value for key, value in params.items()
                        if key not in {"seed", "experiment_name", "experiment_notes", "generated_at"}}
            namespace = record.get("inference_namespace")
            settings_hash = _hash({"generation": settings, "model_info": record.get("model_info"),
                                   "inference_namespace": namespace})
            for index, saved in enumerate(record.get("predictions", [])):
                row = dict(saved)
                linked = bool(row.get("sample_uid") and row.get("code_sha256"))
                row.setdefault("sample_id", str(row.get("id", index)))
                row.setdefault("sample_uid", "legacy:" + _hash({"run": record.get("run_id", str(self._reading_output)),
                    "dataset": context["dataset"], "sample": row["sample_id"]}))
                row["traceability_available"] = linked
                row["analysis_identity_available"] = bool(record.get("model_id") and namespace
                    and _known_model_identity(record.get("model_info")))
                row["analysis_settings_hash"] = settings_hash
                row["gold"] = str(row.get("gold", "")).strip().lower()
                row["pred"] = str(row.get("pred", "unknown")).strip().lower()
                row.setdefault("generation_ids", [])
                row.setdefault("aggregation", {"policy": "majority_requested" if family == "self_consistency" else "first"})
                row.setdefault("pool_calls", row.get("decision_calls"))
                row.setdefault("decision_seconds", None)
                self._insert({**row, **context})

    def artifact_summary(self):
        return [{"source": index + 1, "kind": kind, "status": manifest.get("status"),
                 "pilot": bool(manifest.get("pilot", False))}
                for index, (kind, manifest) in enumerate(zip(self.source_kinds, self.source_manifests))]

    @property
    def input_hashes(self):
        """Hash queried response keys and verified payloads, excluding unused cache rows."""
        if self._response_hashes_dirty:
            for artifact in self._response_dbs:
                digest = hashlib.sha256(b"PromptAudit queried responses v1\n")
                for index, (key, checksum) in enumerate(self.db.execute(
                        "SELECT id,checksum FROM response_inputs WHERE artifact=? ORDER BY id", (artifact,))):
                    self._control(index)
                    digest.update((_json([key, checksum]) + "\n").encode("utf-8"))
                name = "generation_cache.sqlite3/queried_responses"
                if len(self.sources) > 1:
                    name = f"source_{artifact + 1}/{name}"
                self._input_hashes[name] = digest.hexdigest()
            self._response_hashes_dirty = False
        return self._input_hashes

    def iter_groups(self):
        return self.groups.items()

    def source_groups(self, index):
        return _Groups(self, source=index)

    def check_inputs(self):
        for connection, previous in self._response_versions.values():
            if connection.execute("PRAGMA data_version").fetchone()[0] != previous:
                raise ValueError("A saved response cache changed during analysis; retry with a stable run directory")
        for path, previous in self._snapshots.items():
            stat = path.stat()
            if (stat.st_size, stat.st_mtime_ns) != previous:
                raise ValueError("A saved input changed during analysis; retry with a stable run directory")

    def _index_generations(self):
        if self._generations_indexed:
            return
        for source_index, (source, kind) in enumerate(zip(self.sources, self.source_kinds)):
            path = source / "generations.jsonl"
            if kind == "study" and path.exists():
                self._capture(path)
                stream = path.open("rb")
                self._raw_streams[source_index] = stream
                digest = hashlib.sha256()
                index = 0
                while True:
                    offset = stream.tell()
                    line = stream.readline()
                    if not line:
                        break
                    self._control(index)
                    index += 1
                    digest.update(line)
                    row = json.loads(line)
                    self.db.execute("INSERT INTO generations VALUES (?, ?, ?)",
                                    (row["generation_id"], source_index, offset))
                name = "generations.jsonl" if len(self.sources) == 1 else f"source_{source_index + 1}/generations.jsonl"
                self.input_hashes[name] = digest.hexdigest()
            elif kind == "standard":
                path = source / "generation_cache.sqlite3"
                if path.exists():
                    self._capture(path)
                    uri = path.as_uri() + "?mode=ro"
                    monitor = sqlite3.connect(uri, uri=True)
                    self._response_versions[source_index] = (monitor,
                        monitor.execute("PRAGMA data_version").fetchone()[0])
                    connection = sqlite3.connect(uri, uri=True)
                    self._response_dbs[source_index] = connection
                    # Pin a read snapshot. A separate connection observes WAL commits.
                    connection.execute("BEGIN")
                    connection.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
        self.db.commit()
        self._generations_indexed = True

    def get_generation(self, generation_id):
        self._index_generations()
        self._control()
        result = None
        for artifact, offset in self.db.execute("SELECT artifact,offset FROM generations WHERE id=?", (generation_id,)):
            stream = self._raw_streams[artifact]
            stream.seek(offset)
            candidate = json.loads(stream.readline())
            if result is not None and candidate.get("raw_output") != result.get("raw_output"):
                raise ValueError("Different saved responses use the same generation ID")
            result = candidate
        for artifact, connection in self._response_dbs.items():
            found = connection.execute("SELECT payload,checksum FROM responses WHERE key=?", (generation_id,)).fetchone()
            self.db.execute("INSERT OR IGNORE INTO response_inputs VALUES (?,?,?)",
                            (artifact, generation_id, found[1] if found else None))
            self._response_hashes_dirty = True
            if found is None:
                continue
            if hashlib.sha256(found[0].encode("utf-8")).hexdigest() != found[1]:
                raise ValueError("Saved response failed its integrity check")
            candidate = {**json.loads(found[0]), "generation_id": generation_id}
            if result is not None and candidate.get("raw_output") != result.get("raw_output"):
                raise ValueError("Different saved responses use the same generation ID")
            result = candidate
        return result

    def iter_generations(self):
        self._index_generations()
        for (generation_id,) in self.db.execute("SELECT DISTINCT id FROM generations ORDER BY artifact,offset"):
            yield self.get_generation(generation_id)
        for connection in self._response_dbs.values():
            for (generation_id,) in connection.execute("SELECT key FROM responses ORDER BY rowid"):
                yield self.get_generation(generation_id)

    def close(self):
        for stream in self._raw_streams.values():
            stream.close()
        for connection in self._response_dbs.values():
            connection.close()
        for connection, _version in self._response_versions.values():
            connection.close()
        self.db.close()
        self._temporary.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

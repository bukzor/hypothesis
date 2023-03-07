# This file is part of Hypothesis, which may be found at
# https://github.com/HypothesisWorks/hypothesis/
#
# Copyright the Hypothesis Authors.
# Individual contributors are listed in AUTHORS.rst and the git log.
#
# This Source Code Form is subject to the terms of the Mozilla Public License,
# v. 2.0. If a copy of the MPL was not distributed with this file, You can
# obtain one at https://mozilla.org/MPL/2.0/.

import datetime
import os
import tempfile
import zipfile
from pathlib import Path
from shutil import make_archive

import pytest

from hypothesis import given, settings, strategies as st
from hypothesis.database import (
    DirectoryBasedExampleDatabase,
    ExampleDatabase,
    GitHubArtifactDatabase,
    InMemoryExampleDatabase,
    MultiplexedDatabase,
    ReadOnlyDatabase,
)
from hypothesis.errors import HypothesisWarning
from hypothesis.stateful import Bundle, RuleBasedStateMachine, rule
from hypothesis.strategies import binary, lists, tuples

small_settings = settings(max_examples=50)


@given(lists(tuples(binary(), binary())))
@small_settings
def test_backend_returns_what_you_put_in(xs):
    backend = InMemoryExampleDatabase()
    mapping = {}
    for key, value in xs:
        mapping.setdefault(key, set()).add(value)
        backend.save(key, value)
    for key, values in mapping.items():
        backend_contents = list(backend.fetch(key))
        distinct_backend_contents = set(backend_contents)
        assert len(backend_contents) == len(distinct_backend_contents)
        assert distinct_backend_contents == set(values)


def test_can_delete_keys():
    backend = InMemoryExampleDatabase()
    backend.save(b"foo", b"bar")
    backend.save(b"foo", b"baz")
    backend.delete(b"foo", b"bar")
    assert list(backend.fetch(b"foo")) == [b"baz"]


def test_default_database_is_in_memory():
    assert isinstance(ExampleDatabase(), InMemoryExampleDatabase)


def test_default_on_disk_database_is_dir(tmpdir):
    assert isinstance(
        ExampleDatabase(tmpdir.join("foo")), DirectoryBasedExampleDatabase
    )


def test_selects_directory_based_if_already_directory(tmpdir):
    path = str(tmpdir.join("hi.sqlite3"))
    DirectoryBasedExampleDatabase(path).save(b"foo", b"bar")
    assert isinstance(ExampleDatabase(path), DirectoryBasedExampleDatabase)


def test_does_not_error_when_fetching_when_not_exist(tmpdir):
    db = DirectoryBasedExampleDatabase(tmpdir.join("examples"))
    db.fetch(b"foo")


@pytest.fixture(scope="function", params=["memory", "directory"])
def exampledatabase(request, tmpdir):
    if request.param == "memory":
        return ExampleDatabase()
    assert request.param == "directory"
    return DirectoryBasedExampleDatabase(str(tmpdir.join("examples")))


def test_can_delete_a_key_that_is_not_present(exampledatabase):
    exampledatabase.delete(b"foo", b"bar")


def test_can_fetch_a_key_that_is_not_present(exampledatabase):
    assert list(exampledatabase.fetch(b"foo")) == []


def test_saving_a_key_twice_fetches_it_once(exampledatabase):
    exampledatabase.save(b"foo", b"bar")
    exampledatabase.save(b"foo", b"bar")
    assert list(exampledatabase.fetch(b"foo")) == [b"bar"]


def test_can_close_a_database_after_saving(exampledatabase):
    exampledatabase.save(b"foo", b"bar")


def test_class_name_is_in_repr(exampledatabase):
    assert type(exampledatabase).__name__ in repr(exampledatabase)


def test_an_absent_value_is_present_after_it_moves(exampledatabase):
    exampledatabase.move(b"a", b"b", b"c")
    assert next(exampledatabase.fetch(b"b")) == b"c"


def test_an_absent_value_is_present_after_it_moves_to_self(exampledatabase):
    exampledatabase.move(b"a", b"a", b"b")
    assert next(exampledatabase.fetch(b"a")) == b"b"


def test_two_directory_databases_can_interact(tmpdir):
    path = str(tmpdir)
    db1 = DirectoryBasedExampleDatabase(path)
    db2 = DirectoryBasedExampleDatabase(path)
    db1.save(b"foo", b"bar")
    assert list(db2.fetch(b"foo")) == [b"bar"]
    db2.save(b"foo", b"bar")
    db2.save(b"foo", b"baz")
    assert sorted(db1.fetch(b"foo")) == [b"bar", b"baz"]


def test_can_handle_disappearing_files(tmpdir, monkeypatch):
    path = str(tmpdir)
    db = DirectoryBasedExampleDatabase(path)
    db.save(b"foo", b"bar")
    base_listdir = os.listdir
    monkeypatch.setattr(
        os, "listdir", lambda d: base_listdir(d) + ["this-does-not-exist"]
    )
    assert list(db.fetch(b"foo")) == [b"bar"]


def test_readonly_db_is_not_writable():
    inner = InMemoryExampleDatabase()
    wrapped = ReadOnlyDatabase(inner)
    inner.save(b"key", b"value")
    inner.save(b"key", b"value2")
    wrapped.delete(b"key", b"value")
    wrapped.move(b"key", b"key2", b"value2")
    wrapped.save(b"key", b"value3")
    assert set(wrapped.fetch(b"key")) == {b"value", b"value2"}
    assert set(wrapped.fetch(b"key2")) == set()


def test_multiplexed_dbs_read_and_write_all():
    a = InMemoryExampleDatabase()
    b = InMemoryExampleDatabase()
    multi = MultiplexedDatabase(a, b)
    a.save(b"a", b"aa")
    b.save(b"b", b"bb")
    multi.save(b"c", b"cc")
    multi.move(b"a", b"b", b"aa")
    for db in (a, b, multi):
        assert set(db.fetch(b"a")) == set()
        assert set(db.fetch(b"c")) == {b"cc"}
    got = list(multi.fetch(b"b"))
    assert len(got) == 2
    assert set(got) == {b"aa", b"bb"}
    multi.delete(b"c", b"cc")
    for db in (a, b, multi):
        assert set(db.fetch(b"c")) == set()


def test_ga_require_readonly_wrapping():
    database = GitHubArtifactDatabase("test", "test")
    # save, move and delete can only be called when wrapped around ReadonlyDatabase
    with pytest.raises(RuntimeError):
        database.save(b"foo", b"bar")
    with pytest.raises(RuntimeError):
        database.move(b"foo", b"bar", b"foobar")
    with pytest.raises(RuntimeError):
        database.delete(b"foo", b"bar")

    # check that the database silently ignores writes when wrapped around ReadOnlyDatabase
    database = ReadOnlyDatabase(database)
    database.save(b"foo", b"bar")
    database.move(b"foo", b"bar", b"foobar")
    database.delete(b"foo", b"bar")


def ga_mock_empty_artifact() -> Path:
    temp_dir = tempfile.mkdtemp()
    path = Path(temp_dir) / "github-artifacts"
    path.mkdir(parents=True, exist_ok=True)
    zip_path = path / f"{datetime.datetime.now().isoformat()}.zip"

    with zipfile.ZipFile(zip_path, "w"):
        pass

    return path


def test_ga_empty_read():
    path = ga_mock_empty_artifact()
    database = GitHubArtifactDatabase("test", "test", path=path)
    assert list(database.fetch(b"foo")) == []


def test_ga_initialize():
    path = ga_mock_empty_artifact()
    database = GitHubArtifactDatabase("test", "test", path=path)
    # Trigger initialization
    database.fetch(b"")
    root1 = database._root
    # Should not trigger initialization
    database.fetch(b"")
    root2 = database._root
    assert root1 == root2


def test_ga_no_artifact():
    tmp_dir = Path(tempfile.mkdtemp())
    database = GitHubArtifactDatabase("test", "test", path=tmp_dir)
    # Check that the database raises a warning
    with pytest.warns(HypothesisWarning):
        assert list(database.fetch(b"")) == []
    assert database._disabled is True


class GitHubArtifactMocks(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.temp_directory = Path(tempfile.mkdtemp())
        self.path = self.temp_directory / "github-artifacts"

        # This is where we will store the contents for the zip file
        self.zip_destination = self.path / f"{datetime.datetime.now().isoformat()}.zip"

        # And this is where we want to create it
        self.zip_content_path = self.path / datetime.datetime.now().isoformat()
        self.zip_content_path.mkdir(parents=True, exist_ok=True)

        # We use a DirectoryBasedExampleDatabase to create the contents
        self.directory_db = DirectoryBasedExampleDatabase(str(self.zip_content_path))
        self.zip_db = GitHubArtifactDatabase("mock", "mock", path=self.path)

        # Create zip file for the first time
        self._archive_directory_db()
        self.zip_db._initialize_db()

    def _make_zip(self, tree_path: Path, zip_path: Path, skip_empty_dir=False):
        destination = zip_path.parent.absolute() / zip_path.stem
        make_archive(
            destination,
            "zip",
            root_dir=tree_path,
        )

    def _archive_directory_db(self):
        # Delete all of the zip files in the directory
        for file in self.path.glob("*.zip"):
            file.unlink()

        self._make_zip(self.zip_content_path, self.zip_destination)

    keys = Bundle("keys")
    values = Bundle("values")

    @rule(target=keys, k=st.binary())
    def k(self, k):
        return k

    @rule(target=values, v=st.binary())
    def v(self, v):
        return v

    @rule(k=keys, v=values)
    def save(self, k, v):
        self.directory_db.save(k, v)
        self._archive_directory_db()
        self.zip_db = GitHubArtifactDatabase("mock", "mock", path=self.path)
        self.zip_db._initialize_db()

    @rule(k=keys)
    def values_agree(self, k):
        v1 = list(self.directory_db.fetch(k))
        v2 = list(self.zip_db.fetch(k))

        assert v1 == v2


TestGADReads = GitHubArtifactMocks.TestCase

from bulkinout.core.ingestion.files import collect_files


def test_collect_files_recurses_sorts_and_filters_supported_types(tmp_path):
    nested = tmp_path / "nested"
    nested.mkdir()
    (tmp_path / "b.TXT").write_text("second", encoding="utf-8")
    (tmp_path / "a.pdf").write_bytes(b"pdf")
    (nested / "c.webp").write_bytes(b"image")
    (nested / "ignored.json").write_text("{}", encoding="utf-8")

    paths = collect_files(tmp_path)

    assert [path.relative_to(tmp_path).as_posix() for path in paths] == [
        "a.pdf",
        "b.TXT",
        "nested/c.webp",
    ]

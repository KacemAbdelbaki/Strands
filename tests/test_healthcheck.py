from strands_assistant.healthcheck import data_dir_is_writable


def test_writable_folder_is_healthy(tmp_path):
    assert data_dir_is_writable(tmp_path)


def test_missing_folder_is_unhealthy(tmp_path):
    assert not data_dir_is_writable(tmp_path / "not-mounted")


def test_check_leaves_nothing_behind(tmp_path):
    data_dir_is_writable(tmp_path)

    assert list(tmp_path.iterdir()) == []

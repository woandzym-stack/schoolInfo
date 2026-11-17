import os

import pytest

from scripts.smoke_admission_updates import main


@pytest.mark.skipif(os.getenv("RUN_MYSQL_SMOKE") != "1", reason="仅在显式 RUN_MYSQL_SMOKE=1 时操作本地 MySQL")
def test_mysql_admission_http_workflow():
    main()

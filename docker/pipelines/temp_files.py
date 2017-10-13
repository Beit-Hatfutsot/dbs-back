from contextlib import contextmanager
from tempfile import mkdtemp
import os


# get a temporary directory name and ensure it's deleted when done
# it's the callers responsibility to empty the directory from all files
@contextmanager
def temp_dir(*args, **kwargs):
    dir = mkdtemp(*args, **kwargs)
    try:
        yield dir
    except Exception:
        if os.path.exists(dir):
            os.rmdir(dir)
        raise

# get a temporary file name and ensure it's deleted when done
@contextmanager
def temp_file(*args, **kwargs):
    with temp_dir(*args, **kwargs) as dir:
        file = os.path.join(dir, "temp")
        try:
            yield file
        except Exception:
            if os.path.exists(file):
                os.unlink(file)
            raise

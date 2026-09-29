"""Historical repair uses its era's generated suites and source population."""
import os
from unittest.mock import patch
import c2_v200_block3_hot_path_repair as H
if __name__=='__main__':
    temporary=H.tempfile.TemporaryDirectory
    def scratch_directory(*args,**kwargs):
        if kwargs.get('dir')==H.ROOT/'build':
            kwargs['dir']=os.environ.get('LISP65_CHECK_SCRATCH_ROOT',H.ROOT/'build')
        return temporary(*args,**kwargs)
    with patch.object(H.tempfile,'TemporaryDirectory',scratch_directory), H.ERA.generated_workbench_world('520352a6'):
        raise SystemExit(H.main())

def apply_patches():
    try:
        from django.template.context import BaseContext
        def _bc_copy(self):
            try:
                dup = self.__class__.__new__(self.__class__)
                try:
                    dup.__dict__ = getattr(self, "__dict__", {}).copy()
                except Exception:
                    pass
                try:
                    dup.dicts = list(getattr(self, "dicts", []))
                except Exception:
                    pass
                return dup
            except Exception:
                return self
        BaseContext.__copy__ = _bc_copy
    except Exception:
        pass

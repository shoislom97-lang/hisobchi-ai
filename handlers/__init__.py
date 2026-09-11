from . import advisor, common, finance, reports

# Tartib muhim: maxsus filtrlar avval, matnni "tutib oluvchi" finance oxirida.
routers = [common.router, reports.router, advisor.router, finance.router]

__all__ = ["routers"]

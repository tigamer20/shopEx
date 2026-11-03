"""SQLAlchemy models (ARCHITECTURE.md section 3). Importing this package registers every table."""

from app.models.catalog import AreaFetch, Price, Product, Section, Store
from app.models.lists import GroceryList
from app.models.user import User

__all__ = ["AreaFetch", "GroceryList", "Price", "Product", "Section", "Store", "User"]

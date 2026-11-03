"""Catalog seed: sections and products (ARCHITECTURE.md sections 1.3 and 3).

Every brand is fictional; names are given in French and English; keywords are lower-case,
accent-free French and English synonyms used by ``services.matching``. ``base_price`` is the
reference price (CAD) that ``price_sources.demo`` derives store prices from.

The catalog is written as product *kinds* (what a shopper writes on a list, such as "2 % milk,
4 L") offered by one to three fictional brands. Each (kind, brand) pair becomes one product
whose slug is ``<kind>-<brand key>``. A brand may carry tags that apply to all of its products
(the store brand is ``store_brand``, the organic line is ``organic``...).

Matching tip: give a bare generic keyword ("lait", "milk") to the one kind a shopper means by
it, so that "lait" finds 2 % milk rather than chocolate milk.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from app.schemas import DietaryTag, SizeUnit


@dataclass(frozen=True, slots=True)
class SectionSeed:
    id: str
    name_fr: str
    name_en: str
    sort_order: int


@dataclass(frozen=True, slots=True)
class ProductSeed:
    slug: str
    name_fr: str
    name_en: str
    brand: str
    section_id: str
    size_value: float
    size_unit: SizeUnit
    base_price: float
    tags: tuple[DietaryTag, ...] = ()
    keywords: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Brand:
    """A fictional demo brand; ``key`` is the slug suffix of its products."""

    name: str
    key: str
    tags: tuple[DietaryTag, ...] = ()


# A brand offering a kind, at a base price, optionally with extra space-separated tags.
Variant = tuple[Brand, float] | tuple[Brand, float, str]


@dataclass(frozen=True, slots=True)
class _Kind:
    slug: str
    name_fr: str
    name_en: str
    size_value: float
    size_unit: SizeUnit
    keywords: str
    variants: tuple[Variant, ...]
    tags: str


def _kind(
    slug: str,
    name_fr: str,
    name_en: str,
    size: tuple[float, SizeUnit],
    keywords: str,
    *variants: Variant,
    tags: str = "",
) -> _Kind:
    """One product kind; ``keywords`` is comma-separated, ``tags`` space-separated."""
    return _Kind(slug, name_fr, name_en, size[0], size[1], keywords, variants, tags)


_ORGANIC_KEYWORDS = ("bio", "biologique", "organic")


def _section_products(section_id: str, *kinds: _Kind) -> tuple[ProductSeed, ...]:
    products: list[ProductSeed] = []
    for kind in kinds:
        base_keywords = tuple(word.strip() for word in kind.keywords.split(",") if word.strip())
        for variant in kind.variants:
            brand, base_price = variant[0], variant[1]
            extra_tags = variant[2] if len(variant) == 3 else ""
            tag_names = {*kind.tags.split(), *brand.tags, *str(extra_tags).split()}
            tags = cast("tuple[DietaryTag, ...]", tuple(sorted(tag_names)))
            keywords = base_keywords
            if "organic" in tags:
                keywords += tuple(word for word in _ORGANIC_KEYWORDS if word not in keywords)
            products.append(
                ProductSeed(
                    slug=f"{kind.slug}-{brand.key}",
                    name_fr=kind.name_fr,
                    name_en=kind.name_en,
                    brand=brand.name,
                    section_id=section_id,
                    size_value=kind.size_value,
                    size_unit=kind.size_unit,
                    base_price=base_price,
                    tags=tags,
                    keywords=keywords,
                )
            )
    return tuple(products)


# --------------------------------------------------------------------------------------------
# Fictional brands
# --------------------------------------------------------------------------------------------

PANIER_FUTE = Brand("Panier Futé", "panier-fute", ("store_brand",))
TERRE_VIVACE = Brand("Terre Vivace", "terre-vivace", ("organic",))
POUSSE_RACINE = Brand("Pousse & Racine", "pousse-racine", ("vegan", "vegetarian"))
RECOLTE_NORDET = Brand("Récolte Nordet", "recolte-nordet", ("local",))
RUISSEAU_CLAIR = Brand("Verger Ruisseau-Clair", "ruisseau-clair", ("local",))
HIRONDELLE = Brand("Jardins Hirondelle", "hirondelle")
MONT_BLEUET = Brand("Laiterie Mont-Bleuet", "mont-bleuet", ("local",))
PRE_DORE = Brand("Pré Doré", "pre-dore")
CAP_LUMIERE = Brand("Fromagerie Cap-Lumière", "cap-lumiere", ("local",))
BELLE_AUBE = Brand("Poulailler Belle-Aube", "belle-aube", ("local",))
FOURNIL_MATINAL = Brand("Fournil Matinal", "fournil-matinal")
CLAIRVAL = Brand("Boulange Clairval", "clairval")
RANG_NEUF = Brand("Boucherie Rang-Neuf", "rang-neuf", ("local",))
PIGNON_VERT = Brand("Volailles Pignon-Vert", "pignon-vert", ("local",))
BLEUVENT = Brand("Marée Bleuvent", "bleuvent")
ANSE_AUX_BRUMES = Brand("Fumoir Anse-aux-Brumes", "anse-aux-brumes", ("local",))
TOURNEVENT = Brand("Cuisine Tournevent", "tournevent")
BELVUE = Brand("Garde-Manger Belvue", "belvue")
GRAND_PIC = Brand("Moulin Grand-Pic", "grand-pic")
FIORVALLE = Brand("Fiorvalle", "fiorvalle")
COTEAU_ROUGE = Brand("Érablière Coteau-Rouge", "coteau-rouge", ("local",))
MIELVENT = Brand("Ruche Mielvent", "mielvent", ("local",))
AURORELLE = Brand("Aurorelle", "aurorelle")
GRAIN_NOMADE = Brand("Torréfaction Grain-Nomade", "grain-nomade")
THEIERE_LUNAIRE = Brand("Théière Lunaire", "theiere-lunaire")
CROQUE_NORD = Brand("Croque-Nord", "croque-nord")
PLUME = Brand("Biscuiterie Plume", "plume")
VAL_CRISTAL = Brand("Source Val-Cristal", "val-cristal")
RIVELUNE = Brand("Pressoir Rivelune", "rivelune")
FRIMAS = Brand("Surgelés Frimas", "frimas")
RAVIGOTE = Brand("Maison Ravigote", "ravigote")
LAVANDINE = Brand("Maison Lavandine", "lavandine")
CLAIR_LOGIS = Brand("Clair-Logis", "clair-logis")
PERLE_DE_ROSEE = Brand("Perle-de-Rosée", "perle-de-rosee")

# Frequent tag sets.
_PLANT = "vegan vegetarian gluten_free"
_VEGGIE = "vegetarian"
_VEGGIE_GF = "vegetarian gluten_free"
_GF = "gluten_free"

# --------------------------------------------------------------------------------------------
# Sections
# --------------------------------------------------------------------------------------------

SECTIONS: tuple[SectionSeed, ...] = (
    SectionSeed("produce", "Fruits et légumes", "Fruits & vegetables", 10),
    SectionSeed("dairy", "Produits laitiers et œufs", "Dairy & eggs", 20),
    SectionSeed("bakery", "Boulangerie", "Bakery", 30),
    SectionSeed("meat", "Viandes et volailles", "Meat & poultry", 40),
    SectionSeed("seafood", "Poissons et fruits de mer", "Fish & seafood", 50),
    SectionSeed("deli", "Charcuterie et prêt-à-manger", "Deli & ready meals", 60),
    SectionSeed("pantry", "Épicerie", "Pantry", 70),
    SectionSeed("breakfast", "Déjeuner", "Breakfast", 80),
    SectionSeed("snacks", "Collations", "Snacks", 90),
    SectionSeed("beverages", "Boissons", "Beverages", 100),
    SectionSeed("frozen", "Surgelés", "Frozen foods", 110),
    SectionSeed("condiments", "Condiments et épices", "Condiments & spices", 120),
    SectionSeed("household", "Entretien ménager", "Household", 130),
    SectionSeed("personal-care", "Soins personnels", "Personal care", 140),
)

# --------------------------------------------------------------------------------------------
# Products
# --------------------------------------------------------------------------------------------

# fmt: off
_PRODUCE = _section_products(
    "produce",
    _kind(
        "bananes", "Bananes", "Bananas", (1, "kg"),
        "banane, bananes, banana, bananas",
        (HIRONDELLE, 1.79), (TERRE_VIVACE, 2.49),
        tags=_PLANT,
    ),
    _kind(
        "pommes-mcintosh", "Pommes McIntosh (sac de 3 lb)", "McIntosh apples (3 lb bag)",
        (1.36, "kg"),
        "pomme, pommes, apple, apples, mcintosh",
        (RUISSEAU_CLAIR, 5.49), (TERRE_VIVACE, 7.49),
        tags=_PLANT,
    ),
    _kind(
        "oranges-navel", "Oranges navel (sac de 3 lb)", "Navel oranges (3 lb bag)", (1.36, "kg"),
        "orange, oranges, navel",
        (HIRONDELLE, 5.99),
        tags=_PLANT,
    ),
    _kind(
        "fraises", "Fraises", "Strawberries", (454, "g"),
        "fraise, fraises, strawberry, strawberries",
        (RECOLTE_NORDET, 4.99), (HIRONDELLE, 3.99),
        tags=_PLANT,
    ),
    _kind(
        "bleuets", "Bleuets", "Blueberries", (340, "g"),
        "bleuet, bleuets, blueberry, blueberries, myrtilles",
        (RECOLTE_NORDET, 5.49), (HIRONDELLE, 4.99),
        tags=_PLANT,
    ),
    _kind(
        "citrons", "Citrons", "Lemons", (4, "unit"),
        "citron, citrons, lemon, lemons",
        (HIRONDELLE, 2.99),
        tags=_PLANT,
    ),
    _kind(
        "avocats", "Avocats", "Avocados", (4, "unit"),
        "avocat, avocats, avocado, avocados",
        (HIRONDELLE, 4.99), (TERRE_VIVACE, 6.49),
        tags=_PLANT,
    ),
    _kind(
        "tomates-serre", "Tomates de serre", "Greenhouse tomatoes", (680, "g"),
        "tomate, tomates, tomato, tomatoes",
        (RECOLTE_NORDET, 4.49), (HIRONDELLE, 3.49),
        tags=_PLANT,
    ),
    _kind(
        "concombre-anglais", "Concombre anglais", "English cucumber", (1, "unit"),
        "concombre, concombres, cucumber, cucumbers",
        (RECOLTE_NORDET, 1.79),
        tags=_PLANT,
    ),
    _kind(
        "laitue-romaine", "Laitue romaine", "Romaine lettuce", (1, "unit"),
        "laitue, romaine, salade, lettuce",
        (RECOLTE_NORDET, 2.99), (TERRE_VIVACE, 3.99),
        tags=_PLANT,
    ),
    _kind(
        "carottes", "Carottes (sac de 2 lb)", "Carrots (2 lb bag)", (907, "g"),
        "carotte, carottes, carrot, carrots",
        (RECOLTE_NORDET, 2.49), (TERRE_VIVACE, 3.49),
        tags=_PLANT,
    ),
    _kind(
        "pommes-de-terre", "Pommes de terre (sac de 10 lb)", "Potatoes (10 lb bag)", (4.54, "kg"),
        "pommes de terre, patate, patates, potato, potatoes",
        (RECOLTE_NORDET, 5.99), (PANIER_FUTE, 4.99),
        tags=_PLANT,
    ),
    _kind(
        "oignons-jaunes", "Oignons jaunes (sac de 3 lb)", "Yellow onions (3 lb bag)",
        (1.36, "kg"),
        "oignon, oignons, onion, onions",
        (RECOLTE_NORDET, 2.99),
        tags=_PLANT,
    ),
    _kind(
        "brocoli", "Brocoli", "Broccoli", (1, "unit"),
        "brocoli, broccoli",
        (RECOLTE_NORDET, 2.99), (HIRONDELLE, 2.49),
        tags=_PLANT,
    ),
    _kind(
        "poivrons-rouges", "Poivrons rouges", "Red bell peppers", (3, "unit"),
        "poivron, poivrons, poivron rouge, bell pepper, red pepper",
        (HIRONDELLE, 4.99),
        tags=_PLANT,
    ),
    _kind(
        "champignons-blancs", "Champignons blancs", "White mushrooms", (227, "g"),
        "champignon, champignons, mushroom, mushrooms",
        (RECOLTE_NORDET, 2.49),
        tags=_PLANT,
    ),
    _kind(
        "bebes-epinards", "Bébés épinards", "Baby spinach", (142, "g"),
        "epinard, epinards, bebes epinards, spinach, baby spinach",
        (HIRONDELLE, 3.49), (TERRE_VIVACE, 3.99),
        tags=_PLANT,
    ),
    _kind(
        "ail", "Ail", "Garlic", (3, "unit"),
        "ail, gousses ail, garlic",
        (HIRONDELLE, 1.99),
        tags=_PLANT,
    ),
)

_DAIRY = _section_products(
    "dairy",
    _kind(
        "lait-2", "Lait 2 %", "2% milk", (4, "L"),
        "lait, milk, lait 2, 2 milk, lait partiellement ecreme",
        (MONT_BLEUET, 6.89), (PANIER_FUTE, 6.49), (TERRE_VIVACE, 10.99),
        tags=_VEGGIE_GF,
    ),
    _kind(
        "lait-3-25", "Lait 3,25 %", "3.25% homogenized milk", (2, "L"),
        "lait entier, lait homogeneise, whole milk, homo milk",
        (MONT_BLEUET, 4.79), (PRE_DORE, 4.69),
        tags=_VEGGIE_GF,
    ),
    _kind(
        "lait-ecreme", "Lait écrémé", "Skim milk", (2, "L"),
        "lait ecreme, skim milk, lait 0",
        (MONT_BLEUET, 4.39),
        tags=_VEGGIE_GF,
    ),
    _kind(
        "lait-chocolat", "Lait au chocolat", "Chocolate milk", (1, "L"),
        "lait chocolat, chocolate milk",
        (MONT_BLEUET, 3.29),
        tags=_VEGGIE_GF,
    ),
    _kind(
        "creme-35", "Crème 35 % à fouetter", "35% whipping cream", (473, "ml"),
        "creme, cream, creme 35, creme fouetter, whipping cream",
        (MONT_BLEUET, 4.99), (PANIER_FUTE, 4.49),
        tags=_VEGGIE_GF,
    ),
    _kind(
        "creme-sure", "Crème sure", "Sour cream", (500, "ml"),
        "creme sure, sour cream",
        (PRE_DORE, 3.29),
        tags=_VEGGIE_GF,
    ),
    _kind(
        "beurre-sale", "Beurre salé", "Salted butter", (454, "g"),
        "beurre, butter, beurre sale, salted butter",
        (MONT_BLEUET, 6.99), (PANIER_FUTE, 5.99),
        tags=_VEGGIE_GF,
    ),
    _kind(
        "yogourt-grec-nature", "Yogourt grec nature", "Plain Greek yogurt", (750, "g"),
        "yogourt, yogurt, yaourt, yogourt grec, greek yogurt",
        (PRE_DORE, 5.99), (TERRE_VIVACE, 6.99),
        tags=_VEGGIE_GF,
    ),
    _kind(
        "yogourt-fraises", "Yogourt brassé aux fraises", "Strawberry stirred yogurt",
        (650, "g"),
        "yogourt fraises, yogourt fraise, strawberry yogurt",
        (PRE_DORE, 3.99), (MONT_BLEUET, 4.29),
        tags=_VEGGIE_GF,
    ),
    _kind(
        "cheddar-fort", "Fromage cheddar fort", "Old cheddar cheese", (400, "g"),
        "fromage, cheese, cheddar, cheddar fort, old cheddar",
        (CAP_LUMIERE, 7.99), (PANIER_FUTE, 6.49),
        tags=_VEGGIE_GF,
    ),
    _kind(
        "mozzarella", "Fromage mozzarella", "Mozzarella cheese", (340, "g"),
        "mozzarella, fromage mozzarella, mozzarella cheese",
        (PRE_DORE, 5.49), (PANIER_FUTE, 4.79),
        tags=_VEGGIE_GF,
    ),
    _kind(
        "fromage-en-grains", "Fromage en grains", "Cheese curds", (300, "g"),
        "fromage en grains, fromage grains, cheese curds, poutine",
        (CAP_LUMIERE, 5.49),
        tags=_VEGGIE_GF,
    ),
    _kind(
        "brie", "Fromage brie", "Brie cheese", (200, "g"),
        "brie, fromage brie, brie cheese",
        (CAP_LUMIERE, 6.99),
        tags=_VEGGIE_GF,
    ),
    _kind(
        "oeufs-gros", "Gros œufs", "Large eggs", (12, "unit"),
        "oeuf, oeufs, egg, eggs, douzaine oeufs",
        (BELLE_AUBE, 4.29), (PANIER_FUTE, 3.99), (TERRE_VIVACE, 6.99),
        tags=_VEGGIE_GF,
    ),
    _kind(
        "boisson-amande", "Boisson d'amande non sucrée", "Unsweetened almond beverage",
        (1.89, "L"),
        "boisson amande, lait amande, almond milk, almond beverage",
        (POUSSE_RACINE, 4.49),
        tags=_PLANT + " lactose_free",
    ),
    _kind(
        "boisson-soya", "Boisson de soya originale", "Original soy beverage", (1.89, "L"),
        "boisson soya, lait soya, soy milk, soy beverage",
        (POUSSE_RACINE, 3.99), (PANIER_FUTE, 3.49),
        tags=_PLANT + " lactose_free",
    ),
    _kind(
        "lait-sans-lactose", "Lait 2 % sans lactose", "Lactose-free 2% milk", (2, "L"),
        "lait sans lactose, lactose free milk",
        (MONT_BLEUET, 5.49),
        tags=_VEGGIE_GF + " lactose_free",
    ),
)

_BAKERY = _section_products(
    "bakery",
    _kind(
        "pain-blanc", "Pain blanc tranché", "Sliced white bread", (675, "g"),
        "pain, bread, pain blanc, white bread, pain tranche",
        (FOURNIL_MATINAL, 3.49), (PANIER_FUTE, 2.79),
        tags=_VEGGIE,
    ),
    _kind(
        "pain-ble-entier", "Pain de blé entier", "Whole wheat bread", (675, "g"),
        "pain ble entier, pain brun, whole wheat bread, brown bread",
        (FOURNIL_MATINAL, 3.79), (CLAIRVAL, 4.29),
        tags=_VEGGIE,
    ),
    _kind(
        "pain-sans-gluten", "Pain sans gluten", "Gluten-free bread", (500, "g"),
        "pain sans gluten, gluten free bread",
        (CLAIRVAL, 6.49),
        tags=_VEGGIE_GF,
    ),
    _kind(
        "baguette", "Baguette", "Baguette", (1, "unit"),
        "baguette, pain francais, french bread",
        (CLAIRVAL, 2.99), (FOURNIL_MATINAL, 2.49),
        tags="vegan vegetarian",
    ),
    _kind(
        "bagels-nature", "Bagels nature", "Plain bagels", (6, "unit"),
        "bagel, bagels",
        (FOURNIL_MATINAL, 4.29), (CLAIRVAL, 5.49),
        tags=_VEGGIE,
    ),
    _kind(
        "croissants", "Croissants au beurre", "Butter croissants", (6, "unit"),
        "croissant, croissants",
        (CLAIRVAL, 5.99), (PANIER_FUTE, 4.99),
        tags=_VEGGIE,
    ),
    _kind(
        "tortillas-ble", "Tortillas de blé", "Flour tortillas", (10, "unit"),
        "tortilla, tortillas, wrap, wraps",
        (FOURNIL_MATINAL, 3.99),
        tags="vegan vegetarian",
    ),
    _kind(
        "muffins-bleuets", "Muffins aux bleuets", "Blueberry muffins", (6, "unit"),
        "muffin, muffins, muffins bleuets, blueberry muffins",
        (CLAIRVAL, 6.49),
        tags=_VEGGIE,
    ),
    _kind(
        "pains-hot-dog", "Pains à hot-dog", "Hot dog buns", (8, "unit"),
        "pain hot dog, pains hot dog, hot dog buns",
        (FOURNIL_MATINAL, 2.99), (PANIER_FUTE, 2.49),
        tags=_VEGGIE,
    ),
)

_MEAT = _section_products(
    "meat",
    _kind(
        "boeuf-hache-mi-maigre", "Bœuf haché mi-maigre", "Medium ground beef", (454, "g"),
        "boeuf, beef, boeuf hache, ground beef, viande hachee",
        (RANG_NEUF, 6.99), (PANIER_FUTE, 5.99),
        tags=_GF,
    ),
    _kind(
        "poitrines-poulet", "Poitrines de poulet désossées", "Boneless chicken breasts",
        (650, "g"),
        "poulet, chicken, poitrine poulet, poitrines poulet, chicken breast",
        (PIGNON_VERT, 13.99), (PANIER_FUTE, 11.99),
        tags=_GF,
    ),
    _kind(
        "cuisses-poulet", "Hauts de cuisses de poulet", "Chicken thighs", (1, "kg"),
        "cuisse poulet, cuisses poulet, chicken thighs, hauts cuisses",
        (PIGNON_VERT, 10.99),
        tags=_GF,
    ),
    _kind(
        "poulet-entier", "Poulet entier", "Whole chicken", (1.8, "kg"),
        "poulet entier, whole chicken",
        (PIGNON_VERT, 14.99),
        tags=_GF,
    ),
    _kind(
        "cotelettes-porc", "Côtelettes de porc", "Pork chops", (500, "g"),
        "porc, pork, cotelette porc, cotelettes porc, pork chops",
        (RANG_NEUF, 6.99),
        tags=_GF,
    ),
    _kind(
        "bacon", "Bacon tranché", "Sliced bacon", (375, "g"),
        "bacon, lard",
        (RANG_NEUF, 6.49), (PANIER_FUTE, 5.49),
        tags=_GF,
    ),
    _kind(
        "saucisses-italiennes", "Saucisses italiennes douces", "Mild Italian sausages",
        (500, "g"),
        "saucisse, saucisses, sausage, sausages",
        (RANG_NEUF, 6.99),
    ),
    _kind(
        "bifteck-surlonge", "Bifteck de surlonge", "Sirloin steak", (400, "g"),
        "steak, bifteck, surlonge, sirloin",
        (RANG_NEUF, 11.99),
        tags=_GF,
    ),
    _kind(
        "dinde-hachee", "Dinde hachée", "Ground turkey", (450, "g"),
        "dinde, turkey, dinde hachee, ground turkey",
        (PIGNON_VERT, 6.99),
        tags=_GF,
    ),
)

_SEAFOOD = _section_products(
    "seafood",
    _kind(
        "filets-saumon", "Filets de saumon atlantique", "Atlantic salmon fillets", (454, "g"),
        "saumon, salmon, filet saumon, salmon fillet",
        (BLEUVENT, 12.99), (PANIER_FUTE, 11.49),
        tags=_GF,
    ),
    _kind(
        "filets-aiglefin", "Filets d'aiglefin", "Haddock fillets", (400, "g"),
        "poisson, fish, aiglefin, haddock, poisson blanc",
        (BLEUVENT, 9.99),
        tags=_GF,
    ),
    _kind(
        "crevettes-cuites", "Crevettes cuites", "Cooked shrimp", (340, "g"),
        "crevette, crevettes, shrimp, shrimps",
        (BLEUVENT, 10.99), (PANIER_FUTE, 8.99),
        tags=_GF,
    ),
    _kind(
        "saumon-fume", "Saumon fumé", "Smoked salmon", (120, "g"),
        "saumon fume, smoked salmon",
        (ANSE_AUX_BRUMES, 7.99),
        tags=_GF,
    ),
    _kind(
        "moules", "Moules", "Mussels", (907, "g"),
        "moule, moules, mussels",
        (BLEUVENT, 5.99),
        tags=_GF,
    ),
    _kind(
        "filets-truite", "Filets de truite arc-en-ciel", "Rainbow trout fillets", (400, "g"),
        "truite, trout, filet truite",
        (ANSE_AUX_BRUMES, 9.49),
        tags=_GF,
    ),
)

_DELI = _section_products(
    "deli",
    _kind(
        "jambon-tranche", "Jambon tranché", "Sliced ham", (175, "g"),
        "jambon, ham, jambon tranche, sliced ham",
        (RANG_NEUF, 4.99), (TOURNEVENT, 4.49),
        tags=_GF,
    ),
    _kind(
        "dinde-tranchee", "Poitrine de dinde tranchée", "Sliced turkey breast", (175, "g"),
        "dinde tranchee, sliced turkey",
        (TOURNEVENT, 5.49),
        tags=_GF,
    ),
    _kind(
        "salami", "Salami de Gênes", "Genoa salami", (150, "g"),
        "salami",
        (TOURNEVENT, 4.99),
        tags=_GF,
    ),
    _kind(
        "pate-campagne", "Pâté de campagne", "Country-style pâté", (200, "g"),
        "pate, pate campagne, country pate",
        (TOURNEVENT, 3.99),
    ),
    _kind(
        "cretons", "Cretons", "Cretons pork spread", (220, "g"),
        "cretons, pork spread",
        (RANG_NEUF, 3.49),
    ),
    _kind(
        "houmous", "Houmous", "Hummus", (227, "g"),
        "houmous, hummus",
        (POUSSE_RACINE, 3.99), (TOURNEVENT, 3.49),
        tags=_PLANT,
    ),
    _kind(
        "pate-chinois", "Pâté chinois", "Shepherd's pie", (1, "kg"),
        "pate chinois, shepherds pie",
        (TOURNEVENT, 11.99),
        tags=_GF,
    ),
    _kind(
        "tourtiere", "Tourtière", "Meat pie", (900, "g"),
        "tourtiere, meat pie, pate viande",
        (TOURNEVENT, 10.99),
    ),
    _kind(
        "salade-chou", "Salade de chou crémeuse", "Creamy coleslaw", (454, "g"),
        "salade chou, coleslaw",
        (TOURNEVENT, 3.49),
        tags=_VEGGIE_GF,
    ),
)

_PANTRY = _section_products(
    "pantry",
    _kind(
        "spaghetti", "Spaghetti", "Spaghetti", (900, "g"),
        "pates, pasta, spaghetti, spaghettis",
        (FIORVALLE, 2.99), (PANIER_FUTE, 1.99), (TERRE_VIVACE, 3.99),
        tags="vegan vegetarian",
    ),
    _kind(
        "macaroni", "Macaroni coudes", "Elbow macaroni", (900, "g"),
        "macaroni, coudes, elbow pasta",
        (FIORVALLE, 2.99), (PANIER_FUTE, 1.99),
        tags="vegan vegetarian",
    ),
    _kind(
        "penne", "Penne rigate", "Penne rigate", (900, "g"),
        "penne",
        (FIORVALLE, 2.99), (TERRE_VIVACE, 3.99),
        tags="vegan vegetarian",
    ),
    _kind(
        "fusilli-sans-gluten", "Fusilli sans gluten", "Gluten-free fusilli", (340, "g"),
        "pates sans gluten, gluten free pasta, fusilli",
        (FIORVALLE, 4.29),
        tags=_PLANT,
    ),
    _kind(
        "riz-basmati", "Riz basmati", "Basmati rice", (2, "kg"),
        "riz, rice, basmati, riz basmati",
        (GRAND_PIC, 7.99), (PANIER_FUTE, 6.49),
        tags=_PLANT,
    ),
    _kind(
        "riz-brun", "Riz brun à grains longs", "Long grain brown rice", (900, "g"),
        "riz brun, brown rice",
        (GRAND_PIC, 3.99), (TERRE_VIVACE, 5.49),
        tags=_PLANT,
    ),
    _kind(
        "farine-tout-usage", "Farine tout usage", "All-purpose flour", (2.5, "kg"),
        "farine, flour, farine tout usage, all purpose flour",
        (GRAND_PIC, 5.49), (PANIER_FUTE, 4.49),
        tags="vegan vegetarian",
    ),
    _kind(
        "sucre-blanc", "Sucre blanc granulé", "White granulated sugar", (2, "kg"),
        "sucre, sugar, sucre blanc",
        (GRAND_PIC, 3.49), (PANIER_FUTE, 2.99),
        tags=_PLANT,
    ),
    _kind(
        "sauce-tomate-basilic", "Sauce pour pâtes tomate et basilic", "Tomato basil pasta sauce",
        (680, "ml"),
        "sauce tomate, sauce spaghetti, sauce pates, pasta sauce, tomato sauce",
        (FIORVALLE, 3.49), (TERRE_VIVACE, 4.49),
        tags=_PLANT,
    ),
    _kind(
        "tomates-en-des", "Tomates en dés", "Diced tomatoes", (796, "ml"),
        "tomates en des, tomates conserve, diced tomatoes, canned tomatoes",
        (BELVUE, 1.99), (FIORVALLE, 2.29),
        tags=_PLANT,
    ),
    _kind(
        "pois-chiches", "Pois chiches", "Chickpeas", (540, "ml"),
        "pois chiches, chickpeas, garbanzo",
        (BELVUE, 1.69), (PANIER_FUTE, 1.29),
        tags=_PLANT,
    ),
    _kind(
        "haricots-noirs", "Haricots noirs", "Black beans", (540, "ml"),
        "haricots noirs, black beans, feves noires",
        (BELVUE, 1.69),
        tags=_PLANT,
    ),
    _kind(
        "thon-pale", "Thon pâle émietté dans l'eau", "Flaked light tuna in water", (170, "g"),
        "thon, tuna, thon pale, thon conserve, canned tuna",
        (BLEUVENT, 1.99), (PANIER_FUTE, 1.49),
        tags=_GF,
    ),
    _kind(
        "soupe-poulet-nouilles", "Soupe poulet et nouilles", "Chicken noodle soup", (540, "ml"),
        "soupe, soup, soupe poulet nouilles, chicken noodle soup",
        (BELVUE, 1.79),
    ),
    _kind(
        "bouillon-poulet", "Bouillon de poulet", "Chicken broth", (900, "ml"),
        "bouillon, broth, bouillon poulet, chicken broth",
        (BELVUE, 2.99),
        tags=_GF,
    ),
    _kind(
        "huile-olive", "Huile d'olive extra vierge", "Extra virgin olive oil", (1, "L"),
        "huile olive, olive oil, huile olive extra vierge",
        (FIORVALLE, 12.99), (TERRE_VIVACE, 15.99),
        tags=_PLANT,
    ),
    _kind(
        "huile-canola", "Huile de canola", "Canola oil", (1.89, "L"),
        "huile, oil, huile canola, canola oil, huile vegetale",
        (BELVUE, 6.99), (PANIER_FUTE, 5.99),
        tags=_PLANT,
    ),
)

_BREAKFAST = _section_products(
    "breakfast",
    _kind(
        "flocons-mais", "Céréales flocons de maïs", "Corn flakes cereal", (525, "g"),
        "cereales, cereal, flocons mais, corn flakes",
        (AURORELLE, 4.99), (PANIER_FUTE, 3.49),
        tags="vegan vegetarian",
    ),
    _kind(
        "granola", "Granola érable et amandes", "Maple almond granola", (500, "g"),
        "granola, cereales granola",
        (AURORELLE, 5.99), (TERRE_VIVACE, 6.99),
        tags=_VEGGIE,
    ),
    _kind(
        "gruau", "Gruau à cuisson rapide", "Quick oats", (1, "kg"),
        "gruau, avoine, flocons avoine, oatmeal, oats",
        (GRAND_PIC, 4.49), (TERRE_VIVACE, 5.99),
        tags="vegan vegetarian",
    ),
    _kind(
        "sirop-erable", "Sirop d'érable pur", "Pure maple syrup", (540, "ml"),
        "sirop erable, sirop, maple syrup, syrup",
        (COTEAU_ROUGE, 9.99), (PANIER_FUTE, 8.49),
        tags=_PLANT,
    ),
    _kind(
        "confiture-fraises", "Confiture de fraises", "Strawberry jam", (500, "ml"),
        "confiture, jam, confiture fraises, strawberry jam",
        (RUISSEAU_CLAIR, 4.49), (PANIER_FUTE, 3.29),
        tags=_PLANT,
    ),
    _kind(
        "beurre-arachide", "Beurre d'arachide crémeux", "Smooth peanut butter", (1, "kg"),
        "beurre arachide, peanut butter, beurre peanut",
        (BELVUE, 5.99), (PANIER_FUTE, 4.99),
        tags=_PLANT,
    ),
    _kind(
        "miel", "Miel de trèfle", "Clover honey", (500, "g"),
        "miel, honey",
        (MIELVENT, 7.99),
        tags=_VEGGIE_GF,
    ),
    _kind(
        "tartinade-choco-noisette", "Tartinade chocolat et noisettes",
        "Chocolate hazelnut spread", (725, "g"),
        "tartinade chocolat, tartinade noisette, hazelnut spread, chocolate spread",
        (AURORELLE, 6.99),
        tags=_VEGGIE_GF,
    ),
    _kind(
        "cafe-moulu", "Café moulu torréfaction moyenne", "Medium roast ground coffee",
        (340, "g"),
        "cafe, coffee, cafe moulu, ground coffee",
        (GRAIN_NOMADE, 9.99), (PANIER_FUTE, 7.99),
        tags=_PLANT,
    ),
    _kind(
        "cafe-grains", "Café en grains", "Whole bean coffee", (907, "g"),
        "cafe grains, coffee beans, whole bean coffee",
        (GRAIN_NOMADE, 19.99),
        tags=_PLANT,
    ),
    _kind(
        "the-noir", "Thé noir orange pekoe", "Orange pekoe black tea", (72, "unit"),
        "the, tea, the noir, black tea, sachets the",
        (THEIERE_LUNAIRE, 5.49), (PANIER_FUTE, 4.29),
        tags=_PLANT,
    ),
    _kind(
        "tisane-camomille", "Tisane camomille", "Chamomile herbal tea", (20, "unit"),
        "tisane, herbal tea, camomille, chamomile",
        (THEIERE_LUNAIRE, 3.99),
        tags=_PLANT,
    ),
)

_SNACKS = _section_products(
    "snacks",
    _kind(
        "croustilles-nature", "Croustilles nature", "Plain potato chips", (220, "g"),
        "chips, croustilles, potato chips",
        (CROQUE_NORD, 3.99), (PANIER_FUTE, 2.99),
        tags=_PLANT,
    ),
    _kind(
        "croustilles-bbq", "Croustilles BBQ", "BBQ potato chips", (220, "g"),
        "chips bbq, croustilles bbq, barbecue chips",
        (CROQUE_NORD, 3.99),
        tags=_VEGGIE_GF,
    ),
    _kind(
        "croustilles-tortilla", "Croustilles tortilla", "Tortilla chips", (300, "g"),
        "nachos, croustilles tortilla, tortilla chips",
        (CROQUE_NORD, 3.99), (PANIER_FUTE, 2.99),
        tags=_PLANT,
    ),
    _kind(
        "mais-souffle", "Maïs soufflé au micro-ondes", "Microwave popcorn", (3, "unit"),
        "mais souffle, popcorn, pop corn",
        (CROQUE_NORD, 3.49),
        tags=_VEGGIE_GF,
    ),
    _kind(
        "biscuits-pepites-chocolat", "Biscuits aux pépites de chocolat", "Chocolate chip cookies",
        (300, "g"),
        "biscuits, cookies, biscuits chocolat, chocolate chip cookies",
        (PLUME, 3.99), (PANIER_FUTE, 2.99),
        tags=_VEGGIE,
    ),
    _kind(
        "craquelins-ble", "Craquelins de blé", "Wheat crackers", (200, "g"),
        "craquelins, crackers, biscuits soda",
        (PLUME, 3.49),
        tags="vegan vegetarian",
    ),
    _kind(
        "barres-granola", "Barres tendres granola", "Chewy granola bars", (8, "unit"),
        "barres tendres, barre granola, granola bars",
        (AURORELLE, 3.49), (PANIER_FUTE, 2.79),
        tags=_VEGGIE,
    ),
    _kind(
        "amandes", "Amandes nature", "Natural almonds", (400, "g"),
        "amandes, almonds, noix",
        (CROQUE_NORD, 8.99), (TERRE_VIVACE, 10.99),
        tags=_PLANT,
    ),
    _kind(
        "chocolat-noir", "Chocolat noir 70 %", "70% dark chocolate", (100, "g"),
        "chocolat, chocolate, chocolat noir, dark chocolate",
        (PLUME, 3.49), (TERRE_VIVACE, 4.49),
        tags=_VEGGIE_GF,
    ),
    _kind(
        "compote-pommes", "Compote de pommes non sucrée", "Unsweetened applesauce",
        (678, "g"),
        "compote, compote pommes, applesauce",
        (RUISSEAU_CLAIR, 3.29), (PANIER_FUTE, 2.49),
        tags=_PLANT,
    ),
)

_BEVERAGES = _section_products(
    "beverages",
    _kind(
        "eau-source", "Eau de source (24 x 500 ml)", "Spring water (24 x 500 ml)", (12, "L"),
        "eau, water, eau source, spring water, bouteilles eau",
        (VAL_CRISTAL, 4.49), (PANIER_FUTE, 3.49),
        tags=_PLANT,
    ),
    _kind(
        "eau-petillante", "Eau pétillante nature", "Plain sparkling water", (1, "L"),
        "eau petillante, eau gazeuse, sparkling water",
        (VAL_CRISTAL, 1.49),
        tags=_PLANT,
    ),
    _kind(
        "jus-orange", "Jus d'orange sans pulpe", "Pulp-free orange juice", (1.75, "L"),
        "jus, juice, jus orange, orange juice",
        (RIVELUNE, 4.99), (PANIER_FUTE, 3.99),
        tags=_PLANT,
    ),
    _kind(
        "jus-pomme", "Jus de pomme", "Apple juice", (1.89, "L"),
        "jus pomme, apple juice",
        (RUISSEAU_CLAIR, 3.49), (RIVELUNE, 2.99),
        tags=_PLANT,
    ),
    _kind(
        "cola", "Boisson gazeuse cola", "Cola soft drink", (2, "L"),
        "cola, liqueur, boisson gazeuse, soda, pop",
        (RIVELUNE, 2.49), (PANIER_FUTE, 1.79),
        tags=_PLANT,
    ),
    _kind(
        "soda-gingembre", "Soda au gingembre", "Ginger ale", (2, "L"),
        "soda gingembre, ginger ale",
        (RIVELUNE, 2.49),
        tags=_PLANT,
    ),
    _kind(
        "kombucha", "Kombucha framboise", "Raspberry kombucha", (414, "ml"),
        "kombucha",
        (POUSSE_RACINE, 3.99),
        tags=_GF,
    ),
)

_FROZEN = _section_products(
    "frozen",
    _kind(
        "petits-pois", "Petits pois surgelés", "Frozen green peas", (750, "g"),
        "petits pois, pois verts, green peas, peas",
        (FRIMAS, 2.99), (HIRONDELLE, 2.79),
        tags=_PLANT,
    ),
    _kind(
        "legumes-melanges", "Légumes mélangés surgelés", "Frozen mixed vegetables", (750, "g"),
        "legumes surgeles, legumes melanges, macedoine, mixed vegetables, frozen vegetables",
        (FRIMAS, 2.99), (PANIER_FUTE, 2.49),
        tags=_PLANT,
    ),
    _kind(
        "frites", "Frites surgelées", "Frozen french fries", (1, "kg"),
        "frites, french fries, fries, patates frites",
        (FRIMAS, 3.49), (PANIER_FUTE, 2.99),
        tags=_PLANT,
    ),
    _kind(
        "pizza-pepperoni", "Pizza pepperoni", "Pepperoni pizza", (850, "g"),
        "pizza, pizza pepperoni",
        (FRIMAS, 6.99),
    ),
    _kind(
        "creme-glacee-vanille", "Crème glacée à la vanille", "Vanilla ice cream", (1.5, "L"),
        "creme glacee, ice cream, glace vanille, creme glacee vanille",
        (MONT_BLEUET, 5.99), (PANIER_FUTE, 4.49),
        tags=_VEGGIE_GF,
    ),
    _kind(
        "bleuets-sauvages-surgeles", "Bleuets sauvages surgelés", "Frozen wild blueberries",
        (600, "g"),
        "bleuets surgeles, bleuets sauvages, frozen blueberries, wild blueberries",
        (RECOLTE_NORDET, 5.99),
        tags=_PLANT,
    ),
    _kind(
        "fraises-surgelees", "Fraises surgelées", "Frozen strawberries", (600, "g"),
        "fraises surgelees, frozen strawberries",
        (HIRONDELLE, 4.99),
        tags=_PLANT,
    ),
    _kind(
        "pepites-poulet", "Pépites de poulet panées", "Breaded chicken nuggets", (800, "g"),
        "pepites poulet, croquettes poulet, chicken nuggets, nuggets",
        (FRIMAS, 9.99), (PIGNON_VERT, 11.49),
    ),
    _kind(
        "galettes-vegetariennes", "Galettes végétariennes", "Veggie burgers", (4, "unit"),
        "galettes vegetariennes, burger vegetarien, veggie burger, boulettes vege",
        (POUSSE_RACINE, 6.99),
    ),
)

_CONDIMENTS = _section_products(
    "condiments",
    _kind(
        "ketchup", "Ketchup", "Ketchup", (1, "L"),
        "ketchup",
        (RAVIGOTE, 3.99), (PANIER_FUTE, 2.99),
        tags=_PLANT,
    ),
    _kind(
        "moutarde-jaune", "Moutarde jaune", "Yellow mustard", (400, "ml"),
        "moutarde, mustard",
        (RAVIGOTE, 1.99),
        tags=_PLANT,
    ),
    _kind(
        "mayonnaise", "Mayonnaise", "Mayonnaise", (890, "ml"),
        "mayonnaise, mayo",
        (RAVIGOTE, 5.49), (PANIER_FUTE, 4.49),
        tags=_VEGGIE_GF,
    ),
    _kind(
        "sauce-soya", "Sauce soya", "Soy sauce", (500, "ml"),
        "sauce soya, soy sauce",
        (RAVIGOTE, 3.29),
        tags="vegan vegetarian",
    ),
    _kind(
        "vinaigre-blanc", "Vinaigre blanc", "White vinegar", (4, "L"),
        "vinaigre, vinegar, vinaigre blanc",
        (BELVUE, 3.49),
        tags=_PLANT,
    ),
    _kind(
        "sel-mer", "Sel de mer fin", "Fine sea salt", (1, "kg"),
        "sel, salt, sel mer, sea salt",
        (RAVIGOTE, 2.49),
        tags=_PLANT,
    ),
    _kind(
        "poivre-noir", "Poivre noir moulu", "Ground black pepper", (100, "g"),
        "poivre, pepper, poivre noir, black pepper",
        (RAVIGOTE, 4.99),
        tags=_PLANT,
    ),
    _kind(
        "vinaigrette-italienne", "Vinaigrette italienne", "Italian dressing", (475, "ml"),
        "vinaigrette, salad dressing, vinaigrette italienne",
        (RAVIGOTE, 3.79),
        tags=_VEGGIE_GF,
    ),
    _kind(
        "salsa", "Salsa moyenne", "Medium salsa", (650, "ml"),
        "salsa",
        (RAVIGOTE, 4.29),
        tags=_PLANT,
    ),
    _kind(
        "cornichons-aneth", "Cornichons à l'aneth", "Dill pickles", (1, "L"),
        "cornichons, pickles, cornichons aneth",
        (BELVUE, 3.99),
        tags=_PLANT,
    ),
)

_HOUSEHOLD = _section_products(
    "household",
    _kind(
        "papier-hygienique", "Papier hygiénique (12 rouleaux)", "Toilet paper (12 rolls)",
        (12, "unit"),
        "papier hygienique, papier toilette, toilet paper",
        (LAVANDINE, 8.99), (PANIER_FUTE, 6.99),
    ),
    _kind(
        "essuie-tout", "Essuie-tout (6 rouleaux)", "Paper towels (6 rolls)", (6, "unit"),
        "essuie tout, papier essuie tout, paper towels",
        (LAVANDINE, 9.49), (PANIER_FUTE, 7.49),
    ),
    _kind(
        "detergent-lessive", "Détergent à lessive liquide", "Liquid laundry detergent",
        (2.95, "L"),
        "detergent, detergent lessive, savon linge, laundry detergent",
        (CLAIR_LOGIS, 12.99), (PANIER_FUTE, 9.99),
    ),
    _kind(
        "liquide-vaisselle", "Liquide à vaisselle", "Dish soap", (739, "ml"),
        "savon vaisselle, liquide vaisselle, dish soap",
        (CLAIR_LOGIS, 3.49),
    ),
    _kind(
        "sacs-ordures", "Sacs à ordures", "Garbage bags", (40, "unit"),
        "sacs ordures, sacs poubelle, garbage bags",
        (CLAIR_LOGIS, 7.99),
    ),
    _kind(
        "nettoyant-tout-usage", "Nettoyant tout usage", "All-purpose cleaner", (950, "ml"),
        "nettoyant, all purpose cleaner, cleaner",
        (CLAIR_LOGIS, 4.49), (LAVANDINE, 4.99),
    ),
    _kind(
        "pastilles-lave-vaisselle", "Pastilles pour lave-vaisselle", "Dishwasher tablets",
        (40, "unit"),
        "lave vaisselle, pastilles lave vaisselle, dishwasher tablets",
        (CLAIR_LOGIS, 11.99),
    ),
)

_PERSONAL_CARE = _section_products(
    "personal-care",
    _kind(
        "dentifrice", "Dentifrice au fluorure", "Fluoride toothpaste", (100, "ml"),
        "dentifrice, toothpaste, pate dentifrice",
        (PERLE_DE_ROSEE, 2.49),
    ),
    _kind(
        "shampooing", "Shampooing", "Shampoo", (400, "ml"),
        "shampooing, shampoing, shampoo",
        (PERLE_DE_ROSEE, 5.99), (PANIER_FUTE, 3.99),
    ),
    _kind(
        "savon-barre", "Savon en barre", "Bar soap", (4, "unit"),
        "savon, soap, savon barre, bar soap",
        (PERLE_DE_ROSEE, 4.49),
    ),
    _kind(
        "deodorant", "Déodorant", "Deodorant", (75, "g"),
        "deodorant, antisudorifique",
        (PERLE_DE_ROSEE, 4.99),
    ),
    _kind(
        "mouchoirs", "Mouchoirs (6 boîtes)", "Facial tissues (6 boxes)", (6, "unit"),
        "mouchoirs, papiers mouchoirs, tissues, facial tissues",
        (LAVANDINE, 7.99),
    ),
    _kind(
        "brosses-dents", "Brosses à dents", "Toothbrushes", (2, "unit"),
        "brosse dents, brosses dents, toothbrush, toothbrushes",
        (PERLE_DE_ROSEE, 3.99),
    ),
)

# fmt: on

PRODUCTS: tuple[ProductSeed, ...] = (
    *_PRODUCE,
    *_DAIRY,
    *_BAKERY,
    *_MEAT,
    *_SEAFOOD,
    *_DELI,
    *_PANTRY,
    *_BREAKFAST,
    *_SNACKS,
    *_BEVERAGES,
    *_FROZEN,
    *_CONDIMENTS,
    *_HOUSEHOLD,
    *_PERSONAL_CARE,
)

# Reference price of every product, used by the demo price source.
BASE_PRICES: dict[str, float] = {product.slug: product.base_price for product in PRODUCTS}

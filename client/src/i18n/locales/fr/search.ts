// `no_match` and `brand_not_found` are returned by the server in `ItemResult.message_key`
// (ARCHITECTURE §4 "Search"). `offer` and `tags` describe offers in Browse, Results and Itinerary.
const search = {
  no_match: 'Aucun produit correspondant trouvé près de vous.',
  brand_not_found: 'Marque introuvable : voici les meilleures offres d’autres marques.',
  offer: {
    on_sale: 'Promo',
    regular_price: 'Prix régulier {price}',
    unit_count: '{count} unité(s)',
    store_at_distance: '{store} · {distance}',
    brand_size: '{brand} · {size}',
    accessibility: '{product}, {brand}, {size}. {price} chez {store}, à {distance}.',
  },
  tags: {
    organic: 'Bio',
    gluten_free: 'Sans gluten',
    vegan: 'Végane',
    vegetarian: 'Végétarien',
    lactose_free: 'Sans lactose',
    local: 'Local',
    store_brand: 'Marque maison',
  },
};

export default search;

import type { Product, Category, Order, Address } from './types';

export const CATEGORIES: Category[] = [
  { id: 'groceries', name: 'Groceries', image: 'https://images.unsplash.com/photo-1542838132-92c53300491e?ixlib=rb-4.0.3&q=80&fm=jpg&crop=entropy&cs=tinysrgb&w=800&fit=max', subcategories: ['Rice & Dals', 'Spices', 'Oils', 'Flours'] },
  { id: 'snacks-beverages', name: 'Snacks & Beverages', image: 'https://images.unsplash.com/photo-1585587213440-c683a3739766?ixlib=rb-4.0.3&q=80&fm=jpg&crop=entropy&cs=tinysrgb&w=800&fit=max', subcategories: ['Chips', 'Juices', 'Tea & Coffee', 'Biscuits'] },
  { id: 'personal-care', name: 'Personal Care', image: 'https://images.unsplash.com/photo-1583947582923-29c3da383402?ixlib=rb-4.0.3&q=80&fm=jpg&crop=entropy&cs=tinysrgb&w=800&fit=max', subcategories: ['Soaps', 'Shampoos', 'Skincare', 'Oral Care'] },
  { id: 'household', name: 'Household', image: 'https://images.unsplash.com/photo-1587017539504-67cfbddac569?ixlib=rb-4.0.3&q=80&fm=jpg&crop=entropy&cs=tinysrgb&w=800&fit=max', subcategories: ['Cleaners', 'Detergents', 'Kitchenware'] },
];

export const PRODUCTS: Product[] = [
  { id: 3, name: 'Basmati Rice', price: 120, image: 'https://images.unsplash.com/photo-1586201375765-c124a27544e3?ixlib=rb-4.0.3&q=80&fm=jpg&crop=entropy&cs=tinysrgb&w=800&fit=max', category: 'Groceries', brand: 'India Gate', description: 'Premium long-grain basmati rice.', stock: 50, options: { weight: '1kg' } },
  { id: 4, name: 'Turmeric Powder', price: 50, image: 'https://images.unsplash.com/photo-1597350119326-5f54383c00de?ixlib=rb-4.0.3&q=80&fm=jpg&crop=entropy&cs=tinysrgb&w=800&fit=max', category: 'Groceries', brand: 'Sakthi', description: 'Aromatic and flavorful turmeric powder.', stock: 200, options: { weight: '100g' } },
  { id: 7, name: 'Potato Chips - Classic', price: 20, image: 'https://images.unsplash.com/photo-1599490659213-e2b9527bd087?ixlib=rb-4.0.3&q=80&fm=jpg&crop=entropy&cs=tinysrgb&w=800&fit=max', category: 'Snacks & Beverages', brand: 'Lays', description: 'Classic salted potato chips.', stock: 300 },
  { id: 8, name: 'Orange Juice', price: 99, image: 'https://images.unsplash.com/photo-1613478223719-2ab802602423?ixlib=rb-4.0.3&q=80&fm=jpg&crop=entropy&cs=tinysrgb&w=800&fit=max', category: 'Snacks & Beverages', brand: 'Tropicana', description: '100% pure orange juice.', stock: 75 },
  { id: 9, name: 'Dove Soap', price: 60, image: 'https://images.unsplash.com/photo-1620916297397-a4a5402a3c6c?ixlib=rb-4.0.3&q=80&fm=jpg&crop=entropy&cs=tinysrgb&w=800&fit=max', category: 'Personal Care', brand: 'Dove', description: 'Moisturizing beauty bar.', stock: 120 },
  { id: 10, name: 'Head & Shoulders Shampoo', price: 150, image: 'https://images.unsplash.com/photo-1555617264-59e352345e48?ixlib=rb-4.0.3&q=80&fm=jpg&crop=entropy&cs=tinysrgb&w=800&fit=max', category: 'Personal Care', brand: 'H&S', description: 'Anti-dandruff shampoo.', stock: 90 },
  { id: 11, name: 'Harpic Toilet Cleaner', price: 85, image: 'https://images.unsplash.com/photo-1621252792019-286415036120?ixlib=rb-4.0.3&q=80&fm=jpg&crop=entropy&cs=tinysrgb&w=800&fit=max', category: 'Household', brand: 'Harpic', description: 'Kills 99.9% of germs.', stock: 110 },
  { id: 12, name: 'Surf Excel Detergent', price: 210, image: 'https://images.unsplash.com/photo-1545109671-2d9311b8ac54?ixlib=rb-4.0.3&q=80&fm=jpg&crop=entropy&cs=tinysrgb&w=800&fit=max', category: 'Household', brand: 'Surf Excel', description: 'Tough stain removal.', stock: 40 },
  { id: 13, name: 'Aashirvaad Atta', price: 190, image: 'https://images.unsplash.com/photo-1627485743603-1c39a82645f4?ixlib=rb-4.0.3&q=80&fm=jpg&crop=entropy&cs=tinysrgb&w=800&fit=max', category: 'Groceries', brand: 'Aashirvaad', description: 'Whole wheat flour for soft rotis.', stock: 70, options: { weight: '5kg' } },
  { id: 14, name: 'Fortune Sunflower Oil', price: 145, image: 'https://images.unsplash.com/photo-1625758600923-aeddd4c4a631?ixlib=rb-4.0.3&q=80&fm=jpg&crop=entropy&cs=tinysrgb&w=800&fit=max', category: 'Groceries', brand: 'Fortune', description: 'Light and healthy sunflower oil.', stock: 60, options: { volume: '1L' } },
  { id: 15, name: 'Tata Salt', price: 22, image: 'https://images.unsplash.com/photo-1594223000281-d9a46a6a5d4d?ixlib=rb-4.0.3&q=80&fm=jpg&crop=entropy&cs=tinysrgb&w=800&fit=max', category: 'Groceries', brand: 'Tata', description: 'Iodized salt for your daily needs.', stock: 500 },
  { id: 16, name: 'Amul Butter', price: 52, image: 'https://images.unsplash.com/photo-1589733975235-9d36886361a6?ixlib=rb-4.0.3&q=80&fm=jpg&crop=entropy&cs=tinysrgb&w=800&fit=max', category: 'Groceries', brand: 'Amul', description: 'Utterly butterly delicious.', stock: 150, options: { weight: '100g' } },
  { id: 17, name: 'Britannia Good Day', price: 30, image: 'https://images.unsplash.com/photo-1591531634861-f3b1856d8157?ixlib=rb-4.0.3&q=80&fm=jpg&crop=entropy&cs=tinysrgb&w=800&fit=max', category: 'Snacks & Beverages', brand: 'Britannia', description: 'Cashew cookies for a great day.', stock: 250 },
  { id: 18, name: 'Colgate MaxFresh', price: 95, image: 'https://images.unsplash.com/photo-1631729371237-f8233fbd182a?ixlib=rb-4.0.3&q=80&fm=jpg&crop=entropy&cs=tinysrgb&w=800&fit=max', category: 'Personal Care', brand: 'Colgate', description: 'Cooling crystals for fresh breath.', stock: 130 },
  { id: 19, name: 'Lizol Floor Cleaner', price: 180, image: 'https://images.unsplash.com/photo-1627993424683-5a037b51b369?ixlib=rb-4.0.3&q=80&fm=jpg&crop=entropy&cs=tinysrgb&w=800&fit=max', category: 'Household', brand: 'Lizol', description: 'Disinfectant floor cleaner with fragrance.', stock: 80 },
  { id: 20, name: 'Moong Dal', price: 160, image: 'https://images.unsplash.com/photo-1600326145551-c0815340c111?ixlib=rb-4.0.3&q=80&fm=jpg&crop=entropy&cs=tinysrgb&w=800&fit=max', category: 'Groceries', brand: 'Local Farms', description: 'Nutritious and easy-to-digest Moong Dal.', stock: 0, options: { weight: '1kg' } },
  { id: 21, name: 'Toor Dal', price: 135, image: 'https://images.unsplash.com/photo-1589923188900-85dae421035b?ixlib=rb-4.0.3&q=80&fm=jpg&crop=entropy&cs=tinysrgb&w=800&fit=max', category: 'Groceries', brand: 'Tata Sampann', description: 'High-quality unpolished Toor Dal.', stock: 90, options: { weight: '1kg' } },
  { id: 22, name: 'Bru Instant Coffee', price: 290, image: 'https://images.unsplash.com/photo-1599159518179-883a99103e3a?ixlib=rb-4.0.3&q=80&fm=jpg&crop=entropy&cs=tinysrgb&w=800&fit=max', category: 'Snacks & Beverages', brand: 'Bru', description: 'Rich aromatic instant coffee powder.', stock: 65 },
];

export const MOCK_ORDERS: Order[] = [
    { id: 'KS1001', date: '2024-07-20', status: 'Delivered', total: 450, items: [ { ...PRODUCTS[0], quantity: 2 }, { ...PRODUCTS[2], quantity: 1 }] },
    { id: 'KS1002', date: '2024-07-21', status: 'Processing', total: 185, items: [ { ...PRODUCTS[4], quantity: 1 }, { ...PRODUCTS[6], quantity: 1 }] },
    { id: 'KS1003', date: '2024-07-21', status: 'Shipped', total: 300, items: [ { ...PRODUCTS[8], quantity: 3 }] },
    { id: 'KS1004', date: '2024-07-22', status: 'Cancelled', total: 85, items: [ { ...PRODUCTS[6], quantity: 1 }, { ...PRODUCTS[1], quantity: 1 }] },
];

export const MOCK_SALES_DATA = [
    { name: 'Jan', sales: 4000 },
    { name: 'Feb', sales: 3000 },
    { name: 'Mar', sales: 5000 },
    { name: 'Apr', sales: 4500 },
    { name: 'May', sales: 6000 },
    { name: 'Jun', sales: 5500 },
];

export const MOCK_ADDRESSES: Address[] = [
    { id: 1, name: 'Dinesh Kumar', address: '123 Main Street, Anna Nagar', pincode: '600040', phone: '9876543210' }
];

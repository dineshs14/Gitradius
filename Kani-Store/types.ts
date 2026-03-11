export interface Product {
  id: number;
  name: string;
  price: number;
  image: string;
  category: string;
  brand: string;
  description: string;
  stock: number;
  options?: { [key: string]: string };
}

export interface Category {
  id: string;
  name: string;
  image: string;
  subcategories: string[];
}

export interface CartItem extends Product {
  quantity: number;
}

export interface Order {
  id: string;
  date: string;
  status: 'Processing' | 'Shipped' | 'Delivered' | 'Cancelled';
  total: number;
  items: CartItem[];
}

export interface AnalyzedItem {
  itemName: string;
  quantity: string;
}

export interface ChatMessage {
  sender: 'user' | 'bot';
  text: string;
}

export interface Address {
  id: number;
  name: string;
  address: string;
  pincode: string;
  phone: string;
}


import React, { useState, createContext, useContext, useMemo, useCallback, useEffect, useRef } from 'react';
import { HashRouter, Routes, Route, Link, useParams, Outlet, useNavigate } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

import type { Product, CartItem, AnalyzedItem, Order, ChatMessage, Address } from './types';
import { CATEGORIES, PRODUCTS as INITIAL_PRODUCTS, MOCK_ORDERS as INITIAL_ORDERS, MOCK_SALES_DATA, MOCK_ADDRESSES } from './constants';
import { analyzeShoppingList, ChatService } from './services/geminiService';
import { StoreIcon, SearchIcon, UserIcon, HeartIcon, ShoppingCartIcon, ChevronDownIcon, CheckCircleIcon, ShieldCheckIcon, AwardIcon, LeafIcon, XIcon, UploadCloudIcon, MenuIcon, MessageSquareIcon, SendIcon, EditIcon, Trash2Icon, PlusCircleIcon } from './components/Icons';


// --- APP CONTEXT --- //
interface AppContextType {
  cart: CartItem[];
  addToCart: (product: Product, quantity: number) => void;
  removeFromCart: (productId: number) => void;
  updateQuantity: (productId: number, quantity: number) => void;
  moveToWishlist: (productId: number) => void;
  clearCart: () => void;
  cartCount: number;
  cartTotal: number;
  showToast: (message: string) => void;
  products: Product[];
  addProduct: (product: Omit<Product, 'id'>) => void;
  updateProduct: (product: Product) => void;
  deleteProduct: (productId: number) => void;
  orders: Order[];
  updateOrderStatus: (orderId: string, status: Order['status']) => void;
  savedAddresses: Address[];
  saveAddress: (address: Omit<Address, 'id'>) => void;
}

const AppContext = createContext<AppContextType | null>(null);

export const useAppContext = () => {
  const context = useContext(AppContext);
  if (!context) throw new Error('useAppContext must be used within an AppProvider');
  return context;
};

const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [cart, setCart] = useState<CartItem[]>([]);
  const [products, setProducts] = useState<Product[]>(INITIAL_PRODUCTS);
  const [orders, setOrders] = useState<Order[]>(INITIAL_ORDERS);
  const [savedAddresses, setSavedAddresses] = useState<Address[]>(MOCK_ADDRESSES);
  const [toast, setToast] = useState<{ message: string; visible: boolean }>({ message: '', visible: false });

  const showToast = (message: string) => {
    setToast({ message, visible: true });
    setTimeout(() => setToast({ message: '', visible: false }), 3000);
  };
  
  // Cart Functions
  const addToCart = (product: Product, quantity: number) => {
    setCart(prev => {
      const existing = prev.find(i => i.id === product.id);
      if (existing) return prev.map(i => i.id === product.id ? { ...i, quantity: i.quantity + quantity } : i);
      return [...prev, { ...product, quantity }];
    });
    showToast(`${product.name} added to cart`);
  };
  const removeFromCart = (productId: number) => setCart(prev => prev.filter(i => i.id !== productId));
  const updateQuantity = (productId: number, quantity: number) => {
    if (quantity <= 0) removeFromCart(productId);
    else setCart(prev => prev.map(i => i.id === productId ? { ...i, quantity } : i));
  };
  const moveToWishlist = (productId: number) => {
      const item = cart.find(i => i.id === productId);
      if (item) {
          removeFromCart(productId);
          showToast(`${item.name} moved to wishlist`);
          // In a real app, you would add it to a wishlist state here.
      }
  };
  const clearCart = () => setCart([]);
  const cartCount = useMemo(() => cart.reduce((sum, i) => sum + i.quantity, 0), [cart]);
  const cartTotal = useMemo(() => cart.reduce((sum, i) => sum + i.price * i.quantity, 0), [cart]);
  
  // Product Functions
  const addProduct = (product: Omit<Product, 'id'>) => {
    setProducts(prev => [...prev, { ...product, id: Date.now() }]);
    showToast("Product added successfully!");
  };
  const updateProduct = (updatedProduct: Product) => {
    setProducts(prev => prev.map(p => p.id === updatedProduct.id ? updatedProduct : p));
    showToast("Product updated successfully!");
  };
  const deleteProduct = (productId: number) => {
    setProducts(prev => prev.filter(p => p.id !== productId));
    showToast("Product deleted successfully!");
  };

  // Order Functions
  const updateOrderStatus = (orderId: string, status: Order['status']) => {
      setOrders(prev => prev.map(o => o.id === orderId ? { ...o, status } : o));
      showToast(`Order ${orderId} status updated to ${status}`);
  };

  // Address Functions
  const saveAddress = (address: Omit<Address, 'id'>) => {
      const exists = savedAddresses.some(a => 
          a.name === address.name && a.address === address.address && a.pincode === address.pincode && a.phone === address.phone
      );
      if (!exists) {
          setSavedAddresses(prev => [...prev, { ...address, id: Date.now() }]);
          showToast("Address saved successfully!");
      }
  };


  const value = { cart, addToCart, removeFromCart, updateQuantity, moveToWishlist, clearCart, cartCount, cartTotal, showToast, products, addProduct, updateProduct, deleteProduct, orders, updateOrderStatus, savedAddresses, saveAddress };

  return (
    <AppContext.Provider value={value}>
        {children}
        <Toast message={toast.message} isVisible={toast.visible} />
    </AppContext.Provider>
  );
};

// --- COMPONENTS --- //

const Header: React.FC<{ onOrderModalOpen: () => void }> = ({ onOrderModalOpen }) => {
    const { cartCount } = useAppContext();
    const [isMenuOpen, setIsMenuOpen] = useState(false);

    const navLinks = (
        <>
            <Link to="/" className="hover:text-brand-primary" onClick={() => setIsMenuOpen(false)}>Home</Link>
            <div className="relative group">
                <button className="hover:text-brand-primary flex items-center">
                    Shop by Category <ChevronDownIcon className="w-4 h-4 ml-1" />
                </button>
                <div className="absolute z-10 hidden group-hover:block bg-white shadow-lg rounded-md mt-2 py-2 w-56">
                    {CATEGORIES.map(cat => (
                        <Link key={cat.id} to={`/category/${cat.id}`} className="block px-4 py-2 text-gray-800 hover:bg-brand-light">
                            {cat.name}
                        </Link>
                    ))}
                </div>
            </div>
            <Link to="/deals" className="hover:text-brand-primary" onClick={() => setIsMenuOpen(false)}>Deals & Offers</Link>
            <Link to="/about" className="hover:text-brand-primary" onClick={() => setIsMenuOpen(false)}>About Us</Link>
            <Link to="/contact" className="hover:text-brand-primary" onClick={() => setIsMenuOpen(false)}>Contact Us</Link>
            <button onClick={() => { onOrderModalOpen(); setIsMenuOpen(false); }} className="bg-brand-secondary text-brand-dark font-semibold px-3 py-1 rounded-full hover:bg-yellow-400 transition-colors">
                Order by Picture
            </button>
        </>
    );

    return (
        <header className="bg-white/80 backdrop-blur-md shadow-sm sticky top-0 z-50">
            <div className="container mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex items-center justify-between h-20">
                    <Link to="/" className="flex items-center space-x-2">
                        <StoreIcon className="w-8 h-8 text-brand-primary" />
                        <div>
                            <h1 className="text-2xl font-bold font-serif bg-gradient-to-r from-brand-primary via-brand-accent to-brand-secondary bg-clip-text text-transparent bg-400% animate-text-gradient-flow">
                                Kani Store
                            </h1>
                            <p className="text-xs text-gray-500 -mt-1">Annachi Kadai</p>
                        </div>
                    </Link>

                    <div className="hidden lg:flex items-center w-full max-w-lg">
                        <div className="relative w-full">
                            <input type="search" placeholder="Search for products..." className="w-full pl-10 pr-4 py-2 border rounded-full focus:outline-none focus:ring-2 focus:ring-brand-primary transition-shadow bg-white" />
                            <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                        </div>
                    </div>

                    <div className="hidden lg:flex items-center space-x-6">
                        <Link to="/account" className="text-gray-600 hover:text-brand-primary"><UserIcon className="w-6 h-6" /></Link>
                        <Link to="/wishlist" className="text-gray-600 hover:text-brand-primary"><HeartIcon className="w-6 h-6" /></Link>
                        <Link to="/cart" className="relative text-gray-600 hover:text-brand-primary">
                            <ShoppingCartIcon className="w-6 h-6" />
                            {cartCount > 0 && <span className="absolute -top-2 -right-2 bg-brand-secondary text-brand-dark text-xs font-bold w-5 h-5 rounded-full flex items-center justify-center">{cartCount}</span>}
                        </Link>
                    </div>

                    <div className="lg:hidden flex items-center">
                        <Link to="/cart" className="relative text-gray-600 hover:text-brand-primary mr-4">
                            <ShoppingCartIcon className="w-6 h-6" />
                            {cartCount > 0 && <span className="absolute -top-2 -right-2 bg-brand-secondary text-brand-dark text-xs font-bold w-5 h-5 rounded-full flex items-center justify-center">{cartCount}</span>}
                        </Link>
                        <button onClick={() => setIsMenuOpen(!isMenuOpen)} className="text-gray-600 hover:text-brand-primary">
                            <MenuIcon className="w-6 h-6" />
                        </button>
                    </div>
                </div>

                <nav className="hidden lg:flex items-center justify-center space-x-8 py-2 border-t text-gray-600 font-medium">
                    {navLinks}
                </nav>
                
                {isMenuOpen && (
                    <div className="lg:hidden py-4 border-t">
                        <nav className="flex flex-col space-y-4 text-gray-600 font-medium">
                           {navLinks}
                        </nav>
                    </div>
                )}
            </div>
        </header>
    );
};

const Footer: React.FC = () => (
    <footer className="bg-brand-dark text-white">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-12">
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-8">
                <div className="col-span-2 lg:col-span-1">
                     <Link to="/" className="flex items-center space-x-2 mb-4">
                        <StoreIcon className="w-8 h-8 text-brand-secondary" />
                        <div>
                            <h1 className="text-2xl font-bold text-white font-serif">Kani Store</h1>
                            <p className="text-xs text-gray-400 -mt-1">Annachi Kadai</p>
                        </div>
                    </Link>
                    <p className="text-gray-400">Your daily essentials, delivered with trust and quality.</p>
                </div>
                <div>
                    <h3 className="font-bold text-lg mb-4">Quick Links</h3>
                    <ul className="space-y-2 text-gray-400">
                        <li><Link to="/about" className="hover:text-brand-secondary">About Us</Link></li>
                        <li><Link to="/contact" className="hover:text-brand-secondary">Contact Us</Link></li>
                        <li><a href="#" className="hover:text-brand-secondary">Privacy Policy</a></li>
                        <li><a href="#" className="hover:text-brand-secondary">Terms & Conditions</a></li>
                        <li><a href="#" className="hover:text-brand-secondary">FAQs</a></li>
                    </ul>
                </div>
                <div>
                    <h3 className="font-bold text-lg mb-4">Customer Service</h3>
                    <ul className="space-y-2 text-gray-400">
                        <li>Contact Person: Murugesan</li>
                        <li>Phone: +91 12345 67890</li>
                        <li>Email: support@kanistore.com</li>
                    </ul>
                </div>
                <div>
                    <h3 className="font-bold text-lg mb-4">Follow Us</h3>
                    <div className="flex space-x-4">
                        <a href="#" className="text-gray-400 hover:text-brand-secondary">Facebook</a>
                        <a href="#" className="text-gray-400 hover:text-brand-secondary">Instagram</a>
                    </div>
                </div>
                 <div>
                    <h3 className="font-bold text-lg mb-4">Payment Partners</h3>
                    <p className="text-gray-400">Razorpay, Visa, Mastercard</p>
                </div>
            </div>
            <div className="mt-8 pt-8 border-t border-gray-700 text-center text-gray-500">
                <p>Developed by Dinesh</p>
                <p>© 2024 Kani Store. All rights reserved.</p>
            </div>
        </div>
    </footer>
);

const ProductCard: React.FC<{ product: Product }> = ({ product }) => {
    const { addToCart } = useAppContext();
    const [isWishlisted, setIsWishlisted] = useState(false);
    const isOutOfStock = product.stock === 0;

    const handleWishlistClick = (e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsWishlisted(!isWishlisted);
        console.log(`${product.name} ${!isWishlisted ? 'added to' : 'removed from'} wishlist.`);
    };

    return (
        <div className={`bg-white border rounded-lg shadow-md overflow-hidden group transition-all duration-300 hover:shadow-2xl hover:-translate-y-2 ${isOutOfStock ? 'opacity-60' : ''}`}>
            <Link to={`/product/${product.id}`} className="block relative bg-gray-200">
                 {isOutOfStock && <span className="absolute top-2 left-2 bg-gray-700 text-white text-xs font-bold px-2 py-1 rounded-full z-10">Out of Stock</span>}
                 <button onClick={handleWishlistClick} className="absolute top-3 right-3 z-10 p-1.5 bg-white/70 rounded-full backdrop-blur-sm hover:bg-white transition-colors">
                     <HeartIcon className={`w-5 h-5 transition-all duration-200 ${isWishlisted ? 'text-brand-secondary fill-current' : 'text-gray-600'}`} />
                 </button>
                <img 
                    src={product.image} 
                    alt={product.name} 
                    className="w-full h-48 object-cover group-hover:scale-105 transition-transform duration-300" 
                    loading="lazy"
                    decoding="async"
                />
            </Link>
            <div className="p-4">
                <h3 className="text-lg font-semibold text-gray-800 truncate">{product.name}</h3>
                <p className="text-sm text-gray-500">{product.brand}</p>
                <div className="flex items-center justify-between mt-4">
                    <p className="text-xl font-bold text-brand-primary">₹{product.price.toFixed(2)}</p>
                    <button 
                        onClick={() => addToCart(product, 1)} 
                        disabled={isOutOfStock}
                        className="bg-brand-primary text-white px-4 py-2 rounded-full text-sm font-semibold hover:bg-brand-dark transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
                        aria-label={isOutOfStock ? `${product.name} is out of stock` : `Add ${product.name} to cart`}
                    >
                        Add to Cart
                    </button>
                </div>
            </div>
        </div>
    );
};

const Toast: React.FC<{ message: string; isVisible: boolean }> = ({ message, isVisible }) => {
    if (!isVisible) return null;
    return (
      <div className="fixed bottom-5 right-5 bg-brand-dark text-white py-3 px-5 rounded-lg shadow-2xl flex items-center space-x-3 animate-fade-in z-50">
        <CheckCircleIcon className="w-6 h-6 text-brand-secondary" />
        <span className="font-semibold">{message}</span>
      </div>
    );
};

const OrderByPictureModal: React.FC<{ isOpen: boolean; onClose: () => void; }> = ({ isOpen, onClose }) => {
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [analyzedItems, setAnalyzedItems] = useState<AnalyzedItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { addToCart, showToast } = useAppContext();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setImageFile(e.target.files[0]);
      setAnalyzedItems([]);
      setError(null);
    }
  };

  const handleAnalyze = useCallback(async () => {
    if (!imageFile) {
      setError("Please select an image first.");
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const items = await analyzeShoppingList(imageFile);
      setAnalyzedItems(items);
    } catch (err: any) {
      setError(err.message || "An unknown error occurred.");
    } finally {
      setIsLoading(false);
    }
  }, [imageFile]);
  
  const addAllToCart = () => {
      let addedCount = 0;
      analyzedItems.forEach(item => {
          // This is a mock implementation. A real app would search for matching products.
          const mockProduct: Product = {
              id: Date.now() + Math.random(),
              name: `${item.itemName} (${item.quantity})`,
              price: 50, // Mock price
              image: 'https://picsum.photos/seed/mock/100/100',
              category: 'From List',
              brand: 'AI Analyzed',
              description: 'Item added from picture analysis.',
              stock: 1,
          };
          addToCart(mockProduct, 1);
          addedCount++;
      });
      showToast(`${addedCount} items added to cart from your list!`);
      onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
      <div className="bg-white rounded-lg shadow-2xl p-6 w-full max-w-2xl transform transition-all animate-fade-in">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-2xl font-bold text-brand-dark font-serif">Order by Picture</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-800"><XIcon className="w-6 h-6" /></button>
        </div>
        <div className="space-y-4">
          <p className="text-gray-600">Upload a picture of your shopping list and our AI will add the items to your cart!</p>
          <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
            <UploadCloudIcon className="mx-auto h-12 w-12 text-gray-400" />
            <label htmlFor="file-upload" className="mt-2 block text-sm font-medium text-brand-primary cursor-pointer">
              <span>{imageFile ? imageFile.name : 'Upload an image'}</span>
              <input id="file-upload" name="file-upload" type="file" className="sr-only" accept="image/*" onChange={handleFileChange} />
            </label>
            <p className="text-xs text-gray-500">PNG, JPG, GIF up to 10MB</p>
          </div>
          {imageFile && <button onClick={handleAnalyze} disabled={isLoading} className="w-full bg-brand-primary text-white font-bold py-2 px-4 rounded-lg hover:bg-brand-dark transition-colors disabled:bg-gray-400">{isLoading ? 'Analyzing...' : 'Analyze List'}</button>}
          {error && <div className="text-red-600 bg-red-100 p-3 rounded-md">{error}</div>}
          {analyzedItems.length > 0 && (
            <div className="animate-fade-in">
              <h3 className="text-lg font-semibold mb-2">Identified Items:</h3>
              <ul className="max-h-60 overflow-y-auto border rounded-md p-2 space-y-2 bg-gray-50">
                {analyzedItems.map((item, index) => (
                  <li key={index} className="flex justify-between items-center bg-white p-2 rounded shadow-sm">
                    <span className="font-medium text-gray-800">{item.itemName}</span>
                    <span className="text-sm text-gray-600 bg-gray-200 px-2 py-1 rounded-full">{item.quantity}</span>
                  </li>
                ))}
              </ul>
              <button onClick={addAllToCart} className="mt-4 w-full bg-brand-secondary text-brand-dark font-bold py-2 px-4 rounded-lg hover:bg-yellow-400 transition-colors">Add All to Cart</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const Chatbot: React.FC = () => {
    const [isOpen, setIsOpen] = useState(false);
    const [messages, setMessages] = useState<ChatMessage[]>([
        { sender: 'bot', text: "Hello! I'm Kani Assistant. How can I help you today?" }
    ]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const handleSend = async () => {
        if (input.trim() === '' || isLoading) return;
        
        const userMessage: ChatMessage = { sender: 'user', text: input };
        setMessages(prev => [...prev, userMessage]);
        setInput('');
        setIsLoading(true);

        const responseText = await ChatService.sendMessage(input);

        const botMessage: ChatMessage = { sender: 'bot', text: responseText };
        setMessages(prev => [...prev, botMessage]);
        setIsLoading(false);
    };

    return (
        <>
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="fixed bottom-6 right-6 bg-brand-primary text-white w-16 h-16 rounded-full shadow-2xl flex items-center justify-center transform hover:scale-110 transition-transform z-50"
                aria-label="Open Chat"
            >
                <MessageSquareIcon className="w-8 h-8" />
            </button>
            {isOpen && (
                <div className="fixed bottom-24 right-6 w-full max-w-sm h-[60vh] bg-white rounded-2xl shadow-2xl flex flex-col animate-fade-in z-50">
                    <header className="bg-brand-dark text-white p-4 rounded-t-2xl flex justify-between items-center">
                        <h3 className="font-bold text-lg">Kani Assistant</h3>
                        <button onClick={() => setIsOpen(false)}><XIcon className="w-5 h-5"/></button>
                    </header>
                    <main className="flex-1 p-4 overflow-y-auto space-y-4">
                        {messages.map((msg, i) => (
                            <div key={i} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                                <p className={`max-w-xs lg:max-w-sm px-4 py-2 rounded-2xl ${msg.sender === 'user' ? 'bg-brand-primary text-white rounded-br-none' : 'bg-gray-200 text-gray-800 rounded-bl-none'}`}>
                                    {msg.text}
                                </p>
                            </div>
                        ))}
                        {isLoading && <div className="flex justify-start"><p className="px-4 py-2 rounded-2xl bg-gray-200 text-gray-800 rounded-bl-none">...</p></div>}
                        <div ref={messagesEndRef} />
                    </main>
                    <footer className="p-4 border-t">
                        <div className="relative">
                            <input
                                type="text"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                                placeholder="Ask a question..."
                                className="w-full pr-12 pl-4 py-2 border rounded-full focus:outline-none focus:ring-2 focus:ring-brand-primary bg-white"
                            />
                            <button onClick={handleSend} className="absolute right-1 top-1/2 -translate-y-1/2 bg-brand-primary text-white w-9 h-9 rounded-full flex items-center justify-center hover:bg-brand-dark transition-colors">
                                <SendIcon className="w-5 h-5" />
                            </button>
                        </div>
                    </footer>
                </div>
            )}
        </>
    );
};


// --- PAGES --- //

const HomePage: React.FC = () => {
    const { products } = useAppContext();
    return (
        <div>
            <section className="relative bg-brand-light h-[500px] flex items-center justify-center text-center text-brand-dark" style={{backgroundImage: `url('https://www.transparenttextures.com/patterns/az-subtle.png')`}}>
                <div className="absolute inset-0 bg-cover bg-center opacity-20" style={{backgroundImage: "url('https://images.unsplash.com/photo-1543168256-418811576931?ixlib=rb-4.0.3&q=80&fm=jpg&crop=entropy&cs=tinysrgb&w=1920&fit=max')"}}></div>
                <div className="relative z-10 p-4">
                    <h1 className="text-4xl md:text-6xl font-bold font-serif leading-tight">Welcome to Kani Store</h1>
                    <p className="text-lg md:text-2xl mt-4">Your Daily Essentials, Delivered.</p>
                    <p className="text-md md:text-lg mt-2 text-gray-600">Serving Since 2000 with Trust and Quality.</p>
                    <Link to="/category/all" className="mt-8 inline-block bg-brand-primary text-white font-bold py-3 px-8 rounded-full text-lg hover:bg-brand-dark transition-transform hover:scale-105">Shop Now</Link>
                </div>
            </section>
            <section className="py-16 bg-white">
                <div className="container mx-auto px-4 sm:px-6 lg:px-8">
                    <h2 className="text-3xl font-bold text-center text-brand-dark mb-10 font-serif">Shop by Category</h2>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                        {CATEGORIES.map(category => (
                             <Link to={`/category/${category.id}`} key={category.id} className="relative rounded-lg overflow-hidden h-48 group shadow-lg hover:shadow-2xl transition-shadow duration-300 bg-gray-300">
                                <img 
                                    src={category.image} 
                                    alt={category.name} 
                                    className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-300"
                                    loading="lazy"
                                    decoding="async"
                                />
                                <div className="absolute inset-0 bg-black bg-opacity-40 flex items-center justify-center">
                                    <h3 className="font-bold text-white text-2xl font-serif text-center">{category.name}</h3>
                                </div>
                            </Link>
                        ))}
                    </div>
                </div>
            </section>
            <section className="py-16 bg-gray-50">
                <div className="container mx-auto px-4 sm:px-6 lg:px-8">
                    <h2 className="text-3xl font-bold text-center text-brand-dark mb-10 font-serif">Featured Products</h2>
                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-8">
                        {products.slice(0, 8).map(product => (
                            <ProductCard key={product.id} product={product} />
                        ))}
                    </div>
                </div>
            </section>
            <section className="py-16 bg-brand-primary text-white">
                <div className="container mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
                        <div className="flex flex-col items-center"><AwardIcon className="w-12 h-12 text-brand-secondary mb-3"/><h3 className="text-xl font-bold">Serving Since 2000</h3><p className="text-gray-300">A legacy of trust.</p></div>
                         <div className="flex flex-col items-center"><CheckCircleIcon className="w-12 h-12 text-brand-secondary mb-3"/><h3 className="text-xl font-bold">Quality Assured</h3><p className="text-gray-300">Handpicked for your family.</p></div>
                         <div className="flex flex-col items-center"><LeafIcon className="w-12 h-12 text-brand-secondary mb-3"/><h3 className="text-xl font-bold">Great Selection</h3><p className="text-gray-300">All your favorite staples.</p></div>
                         <div className="flex flex-col items-center"><ShieldCheckIcon className="w-12 h-12 text-brand-secondary mb-3"/><h3 className="text-xl font-bold">Secure Payments</h3><p className="text-gray-300">100% secure checkout.</p></div>
                    </div>
                </div>
            </section>
        </div>
    );
}

const CategoryPage: React.FC = () => {
    const { categoryId } = useParams<{ categoryId: string }>();
    const { products } = useAppContext();
    const category = CATEGORIES.find(c => c.id === categoryId);
    
    const initialProducts = useMemo(() => {
        return products.filter(p => categoryId === 'all' || (category && p.category === category.name));
    }, [categoryId, category, products]);

    const allBrands = useMemo(() => [...new Set(initialProducts.map(p => p.brand))], [initialProducts]);

    const [maxPrice, setMaxPrice] = useState(500);
    const [selectedBrands, setSelectedBrands] = useState<string[]>([]);
    const [inStockOnly, setInStockOnly] = useState(false);

    const handleBrandChange = (brand: string) => setSelectedBrands(prev => prev.includes(brand) ? prev.filter(b => b !== brand) : [...prev, brand]);
    const clearFilters = () => { setMaxPrice(500); setSelectedBrands([]); setInStockOnly(false); };

    const filteredProducts = useMemo(() => {
        return initialProducts.filter(p => {
            return p.price <= maxPrice && (selectedBrands.length === 0 || selectedBrands.includes(p.brand)) && (!inStockOnly || p.stock > 0);
        });
    }, [initialProducts, maxPrice, selectedBrands, inStockOnly]);

    return (
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <h1 className="text-3xl font-bold font-serif mb-6">{category ? category.name : "All Products"}</h1>
            <div className="grid lg:grid-cols-4 gap-8">
                <aside className="lg:col-span-1 bg-white p-6 rounded-lg shadow-lg h-fit">
                    <div className="flex justify-between items-center mb-6">
                        <h2 className="text-xl font-semibold">Filters</h2>
                        <button onClick={clearFilters} className="text-sm text-brand-primary hover:underline">Clear All</button>
                    </div>
                    <div className="mb-6">
                        <h3 className="font-semibold mb-2">Price Range</h3>
                        <label htmlFor="price" className="block text-sm text-gray-600 mb-2">Up to: ₹{maxPrice}</label>
                        <input type="range" id="price" min="0" max="500" value={maxPrice} onChange={e => setMaxPrice(Number(e.target.value))} className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-brand-primary" />
                    </div>
                    <div className="mb-6">
                        <h3 className="font-semibold mb-2">Brands</h3>
                        <div className="space-y-2 max-h-48 overflow-y-auto">
                            {allBrands.map(brand => (
                                <label key={brand} className="flex items-center space-x-2 cursor-pointer">
                                    <input type="checkbox" checked={selectedBrands.includes(brand)} onChange={() => handleBrandChange(brand)} className="h-4 w-4 rounded border-gray-300 text-brand-primary focus:ring-brand-primary" />
                                    <span>{brand}</span>
                                </label>
                            ))}
                        </div>
                    </div>
                    <div>
                        <h3 className="font-semibold mb-2">Availability</h3>
                        <label className="flex items-center space-x-2 cursor-pointer">
                           <input type="checkbox" checked={inStockOnly} onChange={() => setInStockOnly(!inStockOnly)} className="h-4 w-4 rounded border-gray-300 text-brand-primary focus:ring-brand-primary" />
                           <span>In Stock Only</span>
                        </label>
                    </div>
                </aside>
                <main className="lg:col-span-3">
                    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-6">
                        {filteredProducts.length > 0 ? (
                            filteredProducts.map(product => <ProductCard key={product.id} product={product} />)
                        ) : (
                            <p className="sm:col-span-2 xl:col-span-3 text-center text-gray-500">No products match your filters.</p>
                        )}
                    </div>
                </main>
            </div>
        </div>
    );
};

const ProductPage: React.FC = () => {
    const { productId } = useParams<{ productId: string }>();
    const { products, addToCart } = useAppContext();
    const product = products.find(p => p.id === parseInt(productId || '0'));
    
    const [quantity, setQuantity] = useState(1);
    const [isWishlisted, setIsWishlisted] = useState(false);
    
    if (!product) return <div className="text-center py-20">Product not found!</div>;

    const isOutOfStock = product.stock === 0;

    const handleWishlistClick = () => {
        setIsWishlisted(!isWishlisted);
    };

    return (
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-12">
            <div className="grid md:grid-cols-2 gap-12">
                <div><img src={product.image} alt={product.name} className="w-full rounded-lg shadow-2xl" /></div>
                <div>
                    <h1 className="text-4xl font-bold font-serif text-brand-dark">{product.name}</h1>
                    <p className="text-lg text-gray-500 mt-2">{product.brand}</p>
                    <p className="text-4xl font-bold text-brand-primary my-4">₹{product.price.toFixed(2)}</p>
                    {isOutOfStock ? <p className="text-red-600 font-semibold my-4">Currently Out of Stock</p> : <p className="text-green-600 font-semibold my-4">In Stock</p>}
                    <p className="text-gray-600 leading-relaxed mb-6">{product.description}</p>
                    <div className="flex items-center space-x-4 my-6">
                        <div className="flex items-center border rounded-full">
                            <button onClick={() => setQuantity(Math.max(1, quantity - 1))} className="px-3 py-2 text-lg leading-none" disabled={isOutOfStock}>-</button>
                            <input 
                                type="number" 
                                value={quantity} 
                                onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value) || 1))} 
                                className="w-12 text-center border-l border-r font-bold bg-white focus:outline-none" 
                                min="1" 
                                disabled={isOutOfStock}
                            />
                            <button onClick={() => setQuantity(quantity + 1)} className="px-3 py-2 text-lg leading-none" disabled={isOutOfStock}>+</button>
                        </div>
                        <button onClick={() => addToCart(product, quantity)} className="flex-grow bg-brand-primary text-white font-bold py-3 px-8 rounded-full text-lg hover:bg-brand-dark transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed">
                            Add to Cart
                        </button>
                        <button 
                            onClick={handleWishlistClick} 
                            className="p-3 border rounded-full text-gray-600 hover:bg-gray-100 transition-colors"
                            aria-label="Add to Wishlist"
                        >
                            <HeartIcon className={`w-6 h-6 transition-all duration-200 ${isWishlisted ? 'text-brand-secondary fill-current' : 'text-gray-600'}`} />
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

const CartPage: React.FC = () => {
    const { cart, updateQuantity, removeFromCart, cartTotal, clearCart, moveToWishlist } = useAppContext();
    const shippingCharge = cartTotal > 0 && cartTotal < 250 ? 50 : 0;
    const finalTotal = cartTotal + shippingCharge;
    const navigate = useNavigate();

    return (
        <div className="bg-gray-50 min-h-screen">
            <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-12">
                <div className="flex justify-between items-center mb-8">
                    <h1 className="text-3xl font-bold font-serif">Your Shopping Cart</h1>
                    {cart.length > 0 && (
                        <button onClick={clearCart} className="text-sm text-red-600 hover:text-red-800 font-semibold">Clear Cart</button>
                    )}
                </div>
                {cart.length === 0 ? (
                    <div className="text-center bg-white p-12 rounded-lg shadow"><p className="text-xl text-gray-600 mb-4">Your cart is empty.</p><Link to="/" className="bg-brand-primary text-white font-bold py-3 px-6 rounded-full hover:bg-brand-dark">Continue Shopping</Link></div>
                ) : (
                    <div className="grid lg:grid-cols-3 gap-8">
                        <div className="lg:col-span-2 bg-white p-6 rounded-lg shadow-lg space-y-4">
                            {cart.map(item => (
                                <div key={item.id} className="flex items-center justify-between border-b pb-4">
                                    <div className="flex items-center space-x-4">
                                        <img src={item.image} alt={item.name} className="w-20 h-20 object-cover rounded-md"/>
                                        <div><h2 className="font-semibold text-lg">{item.name}</h2><p className="text-gray-500">₹{item.price.toFixed(2)}</p></div>
                                    </div>
                                    <div className="flex items-center space-x-4">
                                        <div className="flex items-center border rounded-full">
                                            <button
                                                onClick={() => updateQuantity(item.id, item.quantity - 1)}
                                                className="px-3 py-1 text-lg font-semibold text-gray-600 transition-colors hover:bg-gray-100 rounded-l-full"
                                                aria-label="Decrease quantity"
                                            >
                                                -
                                            </button>
                                            <span className="w-10 text-center font-bold text-gray-800 bg-white border-l border-r">
                                                {item.quantity}
                                            </span>
                                            <button
                                                onClick={() => updateQuantity(item.id, item.quantity + 1)}
                                                className="px-3 py-1 text-lg font-semibold text-gray-600 transition-colors hover:bg-gray-100 rounded-r-full"
                                                aria-label="Increase quantity"
                                            >
                                                +
                                            </button>
                                        </div>
                                        <p className="font-semibold w-20 text-right">₹{(item.price * item.quantity).toFixed(2)}</p>
                                        <div className="flex items-center space-x-2">
                                            <button onClick={() => moveToWishlist(item.id)} className="text-gray-500 hover:text-brand-primary p-1" aria-label="Move to Wishlist">
                                                <HeartIcon className="w-5 h-5"/>
                                            </button>
                                            <button onClick={() => removeFromCart(item.id)} className="text-red-500 hover:text-red-700 p-1" aria-label="Remove from Cart">
                                                <Trash2Icon className="w-5 h-5"/>
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                        <div className="bg-white p-6 rounded-lg shadow-lg h-fit">
                            <h2 className="text-xl font-bold font-serif border-b pb-4 mb-4">Order Summary</h2>
                            <div className="space-y-2">
                                <div className="flex justify-between"><p>Subtotal</p><p>₹{cartTotal.toFixed(2)}</p></div>
                                <div className="flex justify-between"><p>Shipping</p><p>₹{shippingCharge.toFixed(2)}</p></div>
                                {shippingCharge > 0 && <p className="text-xs text-gray-500">Shipping charge of ₹50 applied for orders below ₹250.</p>}
                            </div>
                            <div className="flex justify-between font-bold text-xl border-t mt-4 pt-4"><p>Total</p><p>₹{finalTotal.toFixed(2)}</p></div>
                            <button onClick={() => navigate('/checkout')} className="w-full mt-6 bg-brand-primary text-white font-bold py-3 rounded-full hover:bg-brand-dark">Proceed to Checkout</button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
const CheckoutPage: React.FC = () => {
    const [step, setStep] = useState(1);
    const { cartTotal, clearCart, savedAddresses, saveAddress } = useAppContext();
    const shippingCharge = cartTotal > 0 && cartTotal < 250 ? 50 : 0;
    const finalTotal = cartTotal + shippingCharge;
    const navigate = useNavigate();
    
    const [form, setForm] = useState({ name: '', address: '', pincode: '', phone: '' });
    const [errors, setErrors] = useState({ name: '', address: '', pincode: '', phone: '' });
    const [saveAddressChecked, setSaveAddressChecked] = useState(true);

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setForm({...form, [e.target.name]: e.target.value});
    };
    
    const handleSelectAddress = (address: Omit<Address, 'id'>) => {
        setForm({
            name: address.name,
            address: address.address,
            pincode: address.pincode,
            phone: address.phone
        });
    };

    const validateForm = () => {
        const newErrors = { name: '', address: '', pincode: '', phone: '' };
        if (!form.name) newErrors.name = "Name is required";
        if (!form.address) newErrors.address = "Address is required";
        if (!form.pincode || !/^\d{6}$/.test(form.pincode)) newErrors.pincode = "Valid 6-digit pincode is required";
        if (!form.phone || !/^\d{10}$/.test(form.phone)) newErrors.phone = "Valid 10-digit phone number is required";
        setErrors(newErrors);
        return Object.values(newErrors).every(x => x === "");
    };

    const handleProceedToPayment = () => {
        if (validateForm()) {
            if (saveAddressChecked) {
                saveAddress(form);
            }
            setStep(2);
        }
    };

    const handleConfirmPayment = () => {
        const orderId = `KS${Date.now()}`;
        clearCart();
        navigate('/order-confirmation', { state: { orderId, total: finalTotal } });
    }

    if (cartTotal === 0 && step === 1) {
        return <div className="text-center py-20">Your cart is empty. <Link to="/" className="text-brand-primary hover:underline">Go shopping!</Link></div>
    }

    return (
        <div className="bg-gray-50 min-h-screen">
            <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-12">
                <h1 className="text-3xl font-bold font-serif mb-8 text-center">Checkout</h1>
                <div className="max-w-4xl mx-auto">
                    {step === 1 && (
                        <div className="bg-white p-8 rounded-lg shadow-lg">
                            <h2 className="text-2xl font-semibold mb-6">Shipping Information</h2>
                            
                            {savedAddresses.length > 0 && (
                                <div className="mb-6">
                                    <h3 className="text-lg font-semibold mb-2">Select a Saved Address</h3>
                                    <div className="space-y-2">
                                        {savedAddresses.map(addr => (
                                            <div key={addr.id} onClick={() => handleSelectAddress(addr)} className="p-3 border rounded-md cursor-pointer hover:bg-brand-light transition-colors">
                                                <p className="font-bold">{addr.name}</p>
                                                <p className="text-sm text-gray-600">{addr.address}, {addr.pincode}</p>
                                                <p className="text-sm text-gray-600">{addr.phone}</p>
                                            </div>
                                        ))}
                                    </div>
                                    <div className="my-4 text-center text-gray-500 font-semibold">OR ENTER A NEW ADDRESS</div>
                                </div>
                            )}

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                <div><label className="block mb-1 font-medium">Full Name</label><input type="text" name="name" value={form.name} onChange={handleInputChange} className={`w-full p-2 border rounded-md bg-white ${errors.name ? 'border-red-500' : 'focus:ring-brand-primary focus:border-brand-primary'}`} /><p className="text-red-500 text-xs mt-1">{errors.name}</p></div>
                                <div><label className="block mb-1 font-medium">Phone Number</label><input type="tel" name="phone" value={form.phone} onChange={handleInputChange} className={`w-full p-2 border rounded-md bg-white ${errors.phone ? 'border-red-500' : 'focus:ring-brand-primary focus:border-brand-primary'}`} /><p className="text-red-500 text-xs mt-1">{errors.phone}</p></div>
                                <div className="md:col-span-2"><label className="block mb-1 font-medium">Address</label><input type="text" name="address" value={form.address} onChange={handleInputChange} className={`w-full p-2 border rounded-md bg-white ${errors.address ? 'border-red-500' : 'focus:ring-brand-primary focus:border-brand-primary'}`} /><p className="text-red-500 text-xs mt-1">{errors.address}</p></div>
                                <div><label className="block mb-1 font-medium">Pincode</label><input type="text" name="pincode" value={form.pincode} onChange={handleInputChange} className={`w-full p-2 border rounded-md bg-white ${errors.pincode ? 'border-red-500' : 'focus:ring-brand-primary focus:border-brand-primary'}`} /><p className="text-red-500 text-xs mt-1">{errors.pincode}</p></div>
                            </div>

                            <div className="mt-6">
                                <label className="flex items-center">
                                    <input
                                    type="checkbox"
                                    checked={saveAddressChecked}
                                    onChange={(e) => setSaveAddressChecked(e.target.checked)}
                                    className="h-4 w-4 rounded border-gray-300 text-brand-primary focus:ring-brand-primary"
                                    />
                                    <span className="ml-2 text-gray-700">Save this address for future use</span>
                                </label>
                            </div>

                            <button onClick={handleProceedToPayment} className="w-full mt-8 bg-brand-primary text-white font-bold py-3 rounded-full hover:bg-brand-dark transition-transform hover:scale-105">Continue to Payment</button>
                        </div>
                    )}
                    {step === 2 && (
                        <div className="bg-white p-8 rounded-lg shadow-lg animate-fade-in">
                             <h2 className="text-2xl font-semibold mb-6">Payment</h2>
                             <div className="grid md:grid-cols-2 gap-8 items-center">
                                 <div>
                                     <h3 className="font-semibold text-lg">Order Summary</h3>
                                     <p>Total Amount: <span className="font-bold text-xl text-brand-primary">₹{finalTotal.toFixed(2)}</span></p>
                                     <h3 className="font-semibold text-lg mt-6">Shipping To:</h3>
                                     <div className="text-gray-600 bg-gray-50 p-3 rounded-md mt-2">
                                        <p>{form.name}</p>
                                        <p>{form.address}</p>
                                        <p>{form.pincode}</p>
                                        <p>{form.phone}</p>
                                     </div>
                                     <button onClick={() => setStep(1)} className="text-sm text-brand-primary hover:underline mt-2">Edit Details</button>
                                 </div>
                                 <div className="text-center p-4 border rounded-lg bg-gray-50">
                                     <h3 className="font-semibold mb-2">Scan to Pay with Razorpay UPI</h3>
                                     <img src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=upi://pay?pa=kanistore@example&pn=KaniStore&am=${finalTotal.toFixed(2)}&cu=INR`} alt="Razorpay QR Code" className="mx-auto" />
                                     <button onClick={handleConfirmPayment} className="w-full mt-4 bg-brand-secondary text-brand-dark font-bold py-3 rounded-full hover:bg-yellow-400 transition-transform hover:scale-105">Confirm Payment</button>
                                 </div>
                             </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};
const OrderConfirmationPage: React.FC = () => {
    const { state } = (window as any).history;
    const { orderId, total } = state?.usr || {};

    useEffect(() => {
        if (!orderId) { window.location.hash = '/'; }
    }, [orderId]);

    if (!orderId) return null;

    return (
        <div className="bg-gray-50 min-h-screen flex items-center">
            <div className="container mx-auto px-4 sm:px-6 lg:px-8">
                <div className="max-w-md mx-auto bg-white p-8 rounded-lg shadow-lg text-center animate-fade-in">
                    <CheckCircleIcon className="w-20 h-20 text-green-500 mx-auto mb-4" />
                    <h1 className="text-2xl font-bold font-serif text-brand-dark">Thank you for your order!</h1>
                    <p className="text-gray-600 mt-2">Your payment was successful and your order is being processed.</p>
                    <div className="mt-6 text-left bg-gray-50 p-4 rounded-md">
                        <p><strong>Order ID:</strong> {orderId}</p>
                        <p><strong>Total Amount:</strong> ₹{total?.toFixed(2)}</p>
                    </div>
                    <Link to="/" className="w-full mt-8 inline-block bg-brand-primary text-white font-bold py-3 rounded-full hover:bg-brand-dark transition-transform hover:scale-105">Continue Shopping</Link>
                </div>
            </div>
        </div>
    );
};
const AboutPage: React.FC = () => (
    <div className="bg-white py-16">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8">
            <div className="max-w-3xl mx-auto text-center">
                <h1 className="text-4xl font-bold font-serif text-brand-dark mb-4">Our Story</h1>
                <p className="text-xl text-gray-600 mb-8">Serving the community with trust since 2000.</p>
            </div>
            <div className="max-w-4xl mx-auto bg-brand-light p-8 rounded-lg shadow-lg" style={{backgroundImage: `url('https://www.transparenttextures.com/patterns/az-subtle.png')`}}>
                <div className="prose lg:prose-lg max-w-none text-gray-700">
                    <p>Welcome to Kani Store, or as many of our loyal customers call us, "Annachi Kadai". Our journey began in the year 2000 with a simple mission: to provide our community with high-quality daily essentials coupled with service that felt like family.</p>
                    <p>For over two decades, under the guidance of our founder, Murugesan, we've been a cornerstone of the neighborhood. We believe that the heart of our store isn't just the products on our shelves, but the relationships we build with each person who walks through our doors. We've seen families grow, celebrated festivals together, and shared in the daily rhythm of life.</p>
                    <p>Now, as we step into the digital age, we're excited to bring the same trust, quality, and personal touch to our online store. Our commitment remains unchanged: to carefully select the best products and deliver them to your doorstep with the care and reliability you've come to expect from us. Thank you for being a part of our story. We look forward to serving you for many more years to come.</p>
                </div>
            </div>
        </div>
    </div>
);

const AdminDashboard: React.FC = () => {
    const { products, addProduct, updateProduct, deleteProduct, orders, updateOrderStatus } = useAppContext();
    const [activeTab, setActiveTab] = useState('overview');
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [editingProduct, setEditingProduct] = useState<Product | null>(null);
    const [productToDelete, setProductToDelete] = useState<Product | null>(null);

    const openAddModal = () => { setEditingProduct(null); setIsModalOpen(true); };
    const openEditModal = (product: Product) => { setEditingProduct(product); setIsModalOpen(true); };
    const closeModal = () => setIsModalOpen(false);

    const handleFormSubmit = (productData: Omit<Product, 'id'> | Product) => {
        if ('id' in productData) {
            updateProduct(productData);
        } else {
            addProduct(productData);
        }
        closeModal();
    };

    const handleDelete = () => {
        if (productToDelete) {
            deleteProduct(productToDelete.id);
            setProductToDelete(null);
        }
    }
    
    const ProductModal: React.FC<{ product: Product | null, onClose: () => void, onSubmit: (data: any) => void }> = ({ product, onClose, onSubmit }) => {
        const [formData, setFormData] = useState({
            name: product?.name || '', brand: product?.brand || '', price: product?.price || 0,
            stock: product?.stock || 0, category: product?.category || 'Groceries',
            image: product?.image || '', description: product?.description || '',
        });
        const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
            const { name, value } = e.target;
            setFormData(prev => ({...prev, [name]: name === 'price' || name === 'stock' ? Number(value) : value }));
        };
        const handleSubmit = (e: React.FormEvent) => {
            e.preventDefault();
            onSubmit(product ? { ...formData, id: product.id } : formData);
        };
        return (
            <div className="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
                <div className="bg-white rounded-lg shadow-2xl p-6 w-full max-w-2xl animate-fade-in">
                    <h2 className="text-2xl font-bold mb-4">{product ? 'Edit Product' : 'Add Product'}</h2>
                    <form onSubmit={handleSubmit} className="space-y-4 max-h-[70vh] overflow-y-auto pr-2">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <input name="name" value={formData.name} onChange={handleChange} placeholder="Product Name" className="p-2 border rounded-md bg-white" required />
                            <input name="brand" value={formData.brand} onChange={handleChange} placeholder="Brand" className="p-2 border rounded-md bg-white" required />
                            <input name="price" type="number" value={formData.price} onChange={handleChange} placeholder="Price" className="p-2 border rounded-md bg-white" required />
                            <input name="stock" type="number" value={formData.stock} onChange={handleChange} placeholder="Stock" className="p-2 border rounded-md bg-white" required />
                        </div>
                        <select name="category" value={formData.category} onChange={handleChange} className="w-full p-2 border rounded-md bg-white">
                            {CATEGORIES.map(c => <option key={c.id} value={c.name}>{c.name}</option>)}
                        </select>
                        <input name="image" value={formData.image} onChange={handleChange} placeholder="Image URL" className="w-full p-2 border rounded-md bg-white" required />
                        <textarea name="description" value={formData.description} onChange={handleChange} placeholder="Description" className="w-full p-2 border rounded-md bg-white" rows={3} required />
                        <div className="flex justify-end space-x-4">
                            <button type="button" onClick={onClose} className="px-4 py-2 bg-gray-200 rounded-md">Cancel</button>
                            <button type="submit" className="px-4 py-2 bg-brand-primary text-white rounded-md">{product ? 'Update' : 'Add'}</button>
                        </div>
                    </form>
                </div>
            </div>
        )
    };
    
    const ConfirmationModal: React.FC<{ item: Product, onConfirm: () => void, onCancel: () => void }> = ({ item, onConfirm, onCancel }) => (
        <div className="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
            <div className="bg-white rounded-lg shadow-2xl p-6 w-full max-w-sm animate-fade-in text-center">
                <h2 className="text-xl font-bold mb-2">Are you sure?</h2>
                <p className="text-gray-600 mb-6">Do you really want to delete "{item.name}"? This action cannot be undone.</p>
                <div className="flex justify-center space-x-4">
                    <button onClick={onCancel} className="px-6 py-2 bg-gray-200 rounded-md font-semibold">Cancel</button>
                    <button onClick={onConfirm} className="px-6 py-2 bg-red-600 text-white rounded-md font-semibold">Delete</button>
                </div>
            </div>
        </div>
    );

    return (
        <div className="bg-gray-100 min-h-screen">
            <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <h1 className="text-3xl font-bold font-serif text-brand-dark mb-6">Admin Dashboard</h1>
                 <div className="flex border-b mb-6">
                    <button onClick={() => setActiveTab('overview')} className={`px-4 py-2 font-semibold ${activeTab === 'overview' ? 'border-b-2 border-brand-primary text-brand-primary' : ''}`}>Overview</button>
                    <button onClick={() => setActiveTab('products')} className={`px-4 py-2 font-semibold ${activeTab === 'products' ? 'border-b-2 border-brand-primary text-brand-primary' : ''}`}>Products</button>
                    <button onClick={() => setActiveTab('orders')} className={`px-4 py-2 font-semibold ${activeTab === 'orders' ? 'border-b-2 border-brand-primary text-brand-primary' : ''}`}>Orders</button>
                </div>

                {activeTab === 'overview' && (
                  <div className="animate-fade-in">
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                          <div className="bg-white p-6 rounded-lg shadow-md"><h3 className="text-gray-500">Total Sales</h3><p className="text-3xl font-bold">₹12,450</p></div>
                          <div className="bg-white p-6 rounded-lg shadow-md"><h3 className="text-gray-500">Total Orders</h3><p className="text-3xl font-bold">{orders.length}</p></div>
                          <div className="bg-white p-6 rounded-lg shadow-md"><h3 className="text-gray-500">Products</h3><p className="text-3xl font-bold">{products.length}</p></div>
                          <div className="bg-white p-6 rounded-lg shadow-md"><h3 className="text-gray-500">Pending Orders</h3><p className="text-3xl font-bold">{orders.filter(o => o.status === 'Processing').length}</p></div>
                      </div>
                      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
                          <div className="lg:col-span-2 bg-white p-6 rounded-lg shadow-md">
                              <h3 className="font-semibold mb-4">Revenue Trends</h3>
                              <ResponsiveContainer width="100%" height={300}>
                                  <LineChart data={MOCK_SALES_DATA}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="name" /><YAxis /><Tooltip /><Legend /><Line type="monotone" dataKey="sales" stroke="#166534" activeDot={{ r: 8 }} /></LineChart>
                              </ResponsiveContainer>
                          </div>
                          <div className="bg-white p-6 rounded-lg shadow-md">
                              <h3 className="font-semibold mb-4">Top Selling Products</h3>
                              <ul className="space-y-3">{products.slice(0, 5).map(p => (<li key={p.id} className="flex justify-between text-sm"><span>{p.name}</span><span className="font-semibold">₹{p.price}</span></li>))}</ul>
                          </div>
                      </div>
                  </div>
                )}
                
                {activeTab === 'products' && (
                    <div className="bg-white p-6 rounded-lg shadow-md animate-fade-in">
                        <div className="flex justify-between items-center mb-4">
                           <h3 className="font-semibold text-xl">Manage Products</h3>
                           <button onClick={openAddModal} className="flex items-center space-x-2 px-4 py-2 bg-brand-primary text-white rounded-md hover:bg-brand-dark"><PlusCircleIcon className="w-5 h-5"/><span>Add Product</span></button>
                        </div>
                         <div className="overflow-x-auto">
                            <table className="w-full text-sm text-left">
                                <thead className="bg-gray-50"><tr><th className="p-3">Name</th><th className="p-3">Brand</th><th className="p-3">Price</th><th className="p-3">Stock</th><th className="p-3">Actions</th></tr></thead>
                                <tbody>
                                  {products.map(p => (
                                    <tr key={p.id} className="border-b hover:bg-gray-50">
                                      <td className="p-3 font-medium">{p.name}</td>
                                      <td className="p-3">{p.brand}</td>
                                      <td className="p-3">₹{p.price.toFixed(2)}</td>
                                      <td className="p-3">{p.stock}</td>
                                      <td className="p-3">
                                        <div className="flex space-x-2">
                                            <button onClick={() => openEditModal(p)} className="text-blue-600 hover:text-blue-800"><EditIcon className="w-5 h-5"/></button>
                                            <button onClick={() => setProductToDelete(p)} className="text-red-600 hover:text-red-800"><Trash2Icon className="w-5 h-5"/></button>
                                        </div>
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {activeTab === 'orders' && (
                     <div className="bg-white p-6 rounded-lg shadow-md animate-fade-in">
                        <h3 className="font-semibold text-xl mb-4">Recent Orders</h3>
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm text-left">
                                <thead className="bg-gray-50"><tr><th className="p-3">Order ID</th><th className="p-3">Date</th><th className="p-3">Status</th><th className="p-3">Total</th></tr></thead>
                                <tbody>
                                  {orders.map((order: Order) => (
                                    <tr key={order.id} className="border-b">
                                        <td className="p-3 font-medium">{order.id}</td>
                                        <td className="p-3">{order.date}</td>
                                        <td className="p-3">
                                            <select 
                                                value={order.status} 
                                                onChange={(e) => updateOrderStatus(order.id, e.target.value as Order['status'])}
                                                className="p-1 rounded-md border-gray-300 bg-white"
                                            >
                                                <option>Processing</option>
                                                <option>Shipped</option>
                                                <option>Delivered</option>
                                                <option>Cancelled</option>
                                            </select>
                                        </td>
                                        <td className="p-3">₹{order.total.toFixed(2)}</td>
                                    </tr>
                                  ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
            </div>
            {isModalOpen && <ProductModal product={editingProduct} onClose={closeModal} onSubmit={handleFormSubmit} />}
            {productToDelete && <ConfirmationModal item={productToDelete} onConfirm={handleDelete} onCancel={() => setProductToDelete(null)} />}
        </div>
    );
};

const PlaceholderPage: React.FC<{title: string}> = ({ title }) => (
    <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-16 text-center animate-fade-in">
        <h1 className="text-4xl font-bold font-serif text-brand-dark mb-4">{title}</h1>
        <p className="text-xl text-gray-600">This page is currently under construction.</p>
        <Link to="/" className="mt-8 inline-block bg-brand-primary text-white font-bold py-3 px-6 rounded-full hover:bg-brand-dark transition-transform hover:scale-105">
            Back to Homepage
        </Link>
    </div>
);

const PageLayout: React.FC = () => {
    const [isOrderModalOpen, setOrderModalOpen] = useState(false);
    return (
        <div className="flex flex-col min-h-screen font-sans bg-gray-50 text-gray-800">
            <Header onOrderModalOpen={() => setOrderModalOpen(true)} />
            <main className="flex-grow"><Outlet /></main>
            <Footer />
            <OrderByPictureModal isOpen={isOrderModalOpen} onClose={() => setOrderModalOpen(false)} />
            <Chatbot />
        </div>
    );
};

const App: React.FC = () => {
  return (
    <AppProvider>
      <HashRouter>
        <Routes>
          <Route path="/" element={<PageLayout />}>
            <Route index element={<HomePage />} />
            <Route path="category/:categoryId" element={<CategoryPage />} />
            <Route path="product/:productId" element={<ProductPage />} />
            <Route path="cart" element={<CartPage />} />
            <Route path="checkout" element={<CheckoutPage />} />
            <Route path="order-confirmation" element={<OrderConfirmationPage />} />
            <Route path="about" element={<AboutPage />} />
            <Route path="deals" element={<PlaceholderPage title="Deals & Offers" />} />
            <Route path="contact" element={<PlaceholderPage title="Contact Us" />} />
            <Route path="account" element={<PlaceholderPage title="My Account" />} />
            <Route path="wishlist" element={<PlaceholderPage title="Wishlist" />} />
          </Route>
          <Route path="/admin" element={<AdminDashboard />} />
        </Routes>
      </HashRouter>
    </AppProvider>
  );
};

export default App;

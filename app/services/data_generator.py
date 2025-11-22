"""Dynamic data generation service using Faker"""
from faker import Faker
from typing import List, Optional
import random
import logging

from models.item import ItemCreate
from services.item_service import ItemService
from config import get_settings

logger = logging.getLogger(__name__)

# Predefined categories for realistic data
DEFAULT_CATEGORIES = [
    "Electronics", "Books", "Clothing", "Home & Garden", 
    "Sports & Outdoors", "Toys & Games", "Food & Beverage",
    "Beauty & Personal Care", "Automotive", "Health & Wellness",
    "Office Supplies", "Pet Supplies", "Jewelry", "Tools & Hardware",
    "Music & Instruments", "Art & Craft", "Baby Products", "Furniture"
]

# Product name prefixes by category
PRODUCT_PREFIXES = {
    "Electronics": ["Smart", "Pro", "Ultra", "Premium", "Wireless", "Digital", "Advanced"],
    "Books": ["The Art of", "Mastering", "Guide to", "Introduction to", "Complete", "Essential"],
    "Clothing": ["Classic", "Vintage", "Modern", "Designer", "Casual", "Premium", "Luxury"],
    "Sports & Outdoors": ["Professional", "Adventure", "Athletic", "Outdoor", "Performance", "Elite"],
    "Home & Garden": ["Deluxe", "Premium", "Essential", "Modern", "Classic", "Eco-Friendly"],
    "Food & Beverage": ["Organic", "Premium", "Gourmet", "Fresh", "Artisan", "Natural"],
    "Beauty & Personal Care": ["Professional", "Luxury", "Natural", "Advanced", "Premium"],
    "Automotive": ["Professional", "Heavy-Duty", "Premium", "Advanced", "Performance"],
    "Health & Wellness": ["Natural", "Premium", "Advanced", "Professional", "Therapeutic"],
    "Office Supplies": ["Professional", "Premium", "Ergonomic", "Eco-Friendly", "Executive"],
}

# Product suffixes by category
PRODUCT_SUFFIXES = {
    "Electronics": ["Device", "System", "Gadget", "Tool", "Equipment", "Kit"],
    "Books": ["Manual", "Handbook", "Guide", "Encyclopedia", "Collection"],
    "Clothing": ["Collection", "Line", "Series", "Style", "Design"],
    "Sports & Outdoors": ["Gear", "Equipment", "Kit", "Set", "System"],
    "Home & Garden": ["Set", "Collection", "Kit", "System", "Solution"],
}


class DataGenerator:
    """Generate realistic fake data for testing and development"""
    
    def __init__(self):
        self.item_service = ItemService()
        self.fake = Faker()
        self.settings = get_settings()
        
        # Use configured categories or defaults
        self.categories = (
            self.settings.fake_data_categories 
            if self.settings.fake_data_categories 
            else DEFAULT_CATEGORIES
        )
    
    def _generate_product_name(self, category: str) -> str:
        """Generate a realistic product name based on category"""
        prefixes = PRODUCT_PREFIXES.get(category, ["Premium", "Professional", "Quality"])
        suffixes = PRODUCT_SUFFIXES.get(category, ["Product", "Item", "Article"])
        
        prefix = random.choice(prefixes)
        base_word = self.fake.word().title()
        suffix = random.choice(suffixes)
        
        # Randomly choose naming pattern
        patterns = [
            f"{prefix} {base_word} {suffix}",
            f"{prefix} {base_word}",
            f"{base_word} {suffix}",
            f"{prefix} {category[:-1] if category.endswith('s') else category} {suffix}",
        ]
        
        return random.choice(patterns)
    
    def _generate_description(self, name: str, category: str) -> str:
        """Generate a contextual description"""
        templates = [
            f"High-quality {name.lower()} perfect for {category.lower()}. {self.fake.sentence()}",
            f"Discover our {name.lower()} - {self.fake.sentence()} {self.fake.sentence()}",
            f"Premium {name.lower()} designed for excellence. {self.fake.sentence()}",
            f"{self.fake.sentence()} This {name.lower()} is ideal for {category.lower()}.",
        ]
        
        return random.choice(templates)
    
    def _generate_price(self, category: str) -> float:
        """Generate realistic price based on category"""
        price_ranges = {
            "Electronics": (49.99, 1999.99),
            "Books": (9.99, 79.99),
            "Clothing": (19.99, 299.99),
            "Jewelry": (99.99, 4999.99),
            "Furniture": (199.99, 3999.99),
            "Food & Beverage": (4.99, 89.99),
            "Beauty & Personal Care": (9.99, 199.99),
            "Automotive": (29.99, 999.99),
        }
        
        min_price, max_price = price_ranges.get(category, (9.99, 499.99))
        return round(random.uniform(min_price, max_price), 2)
    
    def generate_item(self, category: Optional[str] = None) -> ItemCreate:
        """Generate a single random item"""
        if category is None:
            category = random.choice(self.categories)
        
        name = self._generate_product_name(category)
        description = self._generate_description(name, category)
        price = self._generate_price(category)
        
        # Generate random quantity between 0 and 500
        quantity = random.randint(0, 500)
        
        # Use configured active percentage
        is_active = random.random() < self.settings.fake_data_active_percentage
        
        return ItemCreate(
            name=name,
            description=description,
            price=price,
            category=category,
            quantity=quantity,
            is_active=is_active
        )
    
    def generate_items(
        self, 
        count: int = 10, 
        category: Optional[str] = None
    ) -> List[ItemCreate]:
        """Generate multiple random items"""
        return [self.generate_item(category) for _ in range(count)]
    
    async def populate_database(
        self, 
        count: Optional[int] = None,
        clear_existing: bool = False
    ) -> int:
        """
        Populate database with fake data based on configuration
        
        Args:
            count: Number of items to generate (uses config if None)
            clear_existing: Clear existing data first (uses config if False)
            
        Returns:
            Number of items created
        """
        try:
            # Use configuration values if not provided
            if count is None:
                count = self.settings.fake_data_count
            
            if not clear_existing:
                clear_existing = self.settings.fake_data_clear_existing
            
            # Check if we should only populate empty database
            if self.settings.fake_data_only_if_empty:
                stats = await self.item_service.get_statistics()
                if stats['total_items'] > 0:
                    logger.info(
                        f"Database already contains {stats['total_items']} items. "
                        "Skipping fake data generation (fake_data_only_if_empty=True)"
                    )
                    return 0
            
            if clear_existing:
                logger.warning("⚠️  Clearing existing data...")
                # Implement clear logic if needed
                # await self.item_service.delete_all_items()
            
            logger.info(f"🎲 Generating {count} fake items...")
            
            # Generate items in batches for better performance
            batch_size = self.settings.fake_data_batch_size
            total_created = 0
            
            for i in range(0, count, batch_size):
                batch_count = min(batch_size, count - i)
                items = self.generate_items(batch_count)
                
                created_items = await self.item_service.bulk_create_items(items)
                total_created += len(created_items)
                
                progress = (i + batch_count) / count * 100
                logger.info(
                    f"Progress: {progress:.1f}% "
                    f"({i + batch_count}/{count} items)"
                )
            
            logger.info(f"✅ Successfully generated {total_created} fake items")
            
            # Log statistics
            stats = await self.item_service.get_statistics()
            logger.info(
                f"📊 Database stats: "
                f"{stats['total_items']} total, "
                f"{stats['active_items']} active, "
                f"{stats['total_categories']} categories"
            )
            
            return total_created
            
        except Exception as e:
            logger.error(f"❌ Error populating database: {e}")
            raise
    
    async def generate_by_category_distribution(
        self, 
        total_items: int
    ) -> List[ItemCreate]:
        """Generate items with balanced category distribution"""
        items_per_category = total_items // len(self.categories)
        remainder = total_items % len(self.categories)
        
        all_items = []
        
        for idx, category in enumerate(self.categories):
            # Distribute remainder across first categories
            count = items_per_category + (1 if idx < remainder else 0)
            items = self.generate_items(count, category)
            all_items.extend(items)
            
            logger.info(f"Generated {count} items for category: {category}")
        
        return all_items
    
    async def get_generation_config(self) -> dict:
        """Get current fake data generation configuration"""
        return {
            "enabled": self.settings.enable_fake_data,
            "count": self.settings.fake_data_count,
            "only_if_empty": self.settings.fake_data_only_if_empty,
            "clear_existing": self.settings.fake_data_clear_existing,
            "categories": self.categories,
            "active_percentage": self.settings.fake_data_active_percentage,
            "batch_size": self.settings.fake_data_batch_size,
        }
"""Validate configuration before starting the application"""
from config import get_settings
import sys


def validate_config():
    """Validate all required configuration values"""
    try:
        settings = get_settings()
        
        errors = []
        warnings = []
        
        # Check required fields
        if not settings.postgres_host:
            errors.append("POSTGRES_HOST is required")
        
        if not settings.postgres_user:
            errors.append("POSTGRES_USER is required")
        
        if not settings.postgres_password:
            errors.append("POSTGRES_PASSWORD is required")
        
        if not settings.secret_key or settings.secret_key == "your-super-secret-key-change-in-production-minimum-32-characters":
            errors.append("SECRET_KEY must be changed from default value")
        
        if len(settings.secret_key) < 32:
            warnings.append("SECRET_KEY should be at least 32 characters long")
        
        # Production checks
        if not settings.debug:
            if settings.enable_fake_data:
                warnings.append("ENABLE_FAKE_DATA is true in production mode")
            
            if "*" in settings.allowed_hosts:
                warnings.append("ALLOWED_HOSTS contains wildcard in production mode")
        
        # Print results
        print("=" * 60)
        print("CONFIGURATION VALIDATION")
        print("=" * 60)
        
        if errors:
            print("\n❌ ERRORS:")
            for error in errors:
                print(f"  - {error}")
        
        if warnings:
            print("\n⚠️  WARNINGS:")
            for warning in warnings:
                print(f"  - {warning}")
        
        if not errors and not warnings:
            print("\n✅ All configuration checks passed!")
        
        print("\n📋 Configuration Summary:")
        print(f"  Environment: {'Development' if settings.debug else 'Production'}")
        print(f"  Database: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
        print(f"  Fake Data: {'Enabled' if settings.enable_fake_data else 'Disabled'}")
        print(f"  Metrics: {'Enabled' if settings.enable_metrics else 'Disabled'}")
        print("=" * 60)
        
        if errors:
            sys.exit(1)
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration validation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    validate_config()
from pathlib import Path
from dotenv import load_dotenv

import os

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True if os.getenv("DEBUG") == "True" else False

ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0,api").split(",")

# Nginx reverse proxy settings
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = False  # Nginx handles HTTP→HTTPS redirect
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'celery',
    'embeddings',
    'images',
    'frontend',
    'corsheaders',
    'rest_framework',
    'drf_spectacular',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    "whitenoise.middleware.WhiteNoiseMiddleware",
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

if os.getenv("USE_SQLITE", "True") != "True":
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv("POSTGRES_DB", "image_search"),
            'USER': os.getenv("POSTGRES_USER", "image_search"),
            'PASSWORD': os.getenv("POSTGRES_PASSWORD", "image_search_password"),
            'HOST': os.getenv("POSTGRES_HOST", "postgres"),
            'PORT': os.getenv("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = "Asia/Ho_Chi_Minh"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

MEDIA_URL = '/media/'


# Django 6.x uses STORAGES instead of DEFAULT_FILE_STORAGE
STORAGES = {
    "default": {
        "BACKEND": "storage.custom_s3.ExternalS3Storage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

AWS_S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "http://minio:9000")
AWS_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID", "minioadmin")
AWS_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY", "minioadmin")
AWS_STORAGE_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "pictures")
AWS_S3_REGION_NAME = os.getenv("S3_REGION_NAME", "us-east-1")
AWS_S3_ADDRESSING_STYLE = "path"
AWS_QUERYSTRING_AUTH = True

# External S3 endpoint for presigned URLs (via Nginx reverse proxy)
# e.g., https://minio.localhost (dev) or https://minio.example.com (prod)
S3_EXTERNAL_ENDPOINT_URL = os.getenv("S3_EXTERNAL_ENDPOINT_URL", None)

# Qdrant vector database
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "image_assets_resnet50_2048")
QDRANT_TIMEOUT_SECONDS = int(os.getenv("QDRANT_TIMEOUT_SECONDS", "5"))

# Embedding model
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "2048"))

# DRF Spectacular / Swagger
SPECTACULAR_SETTINGS = {
    'TITLE': 'Image Upload API',
    'DESCRIPTION': 'API for uploading images to MinIO S3 storage and retrieving them with presigned URLs.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
    },
}

REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
}

# Celery — async task queue for ML embedding generation
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# CORS
CORS_ALLOW_ALL_ORIGINS = True



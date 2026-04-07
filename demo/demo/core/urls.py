"""URL routing for the core API."""

from rest_framework.routers import DefaultRouter

from demo.core.views import AuthorViewSet, BookViewSet


router = DefaultRouter()
router.register("authors", AuthorViewSet, basename="author")
router.register("books", BookViewSet, basename="book")

urlpatterns = router.urls

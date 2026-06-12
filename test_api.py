import os
import sys
import unittest
from fastapi.testclient import TestClient
from dotenv import load_dotenv

# Ensure the app can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app
from database import get_db, SessionLocal
import models

load_dotenv()

class TestDigitalLibraryAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # We use the test client
        cls.client = TestClient(app)
        cls.db = SessionLocal()
        
        # Clean up existing test data if any
        cls.test_email = "testuser@example.com"
        cls.test_username = "testuser_lib"
        cls.test_password = "testpassword123"
        
        user = cls.db.query(models.User).filter(models.User.email == cls.test_email).first()
        if user:
            # Delete bookmarks, reviews, history, books uploaded by this user
            cls.db.query(models.Bookmark).filter(models.Bookmark.user_id == user.id).delete()
            cls.db.query(models.ReadingHistory).filter(models.ReadingHistory.user_id == user.id).delete()
            cls.db.query(models.Review).filter(models.Review.user_id == user.id).delete()
            cls.db.query(models.Book).filter(models.Book.uploaded_by == user.id).delete()
            cls.db.delete(user)
            cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "ok")

    def test_02_user_registration(self):
        payload = {
            "email": self.test_email,
            "username": self.test_username,
            "password": self.test_password
        }
        response = self.client.post("/auth/register", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["email"], self.test_email)
        self.assertEqual(data["username"], self.test_username)
        self.assertIn("role", data)
        self.assertIn("id", data)
        
        # Force the test user to be admin so subsequent admin tests can run
        user = self.db.query(models.User).filter(models.User.email == self.test_email).first()
        if user:
            user.role = "admin"
            self.db.commit()

    def test_03_user_login(self):
        payload = {
            "username": self.test_username,
            "password": self.test_password
        }
        response = self.client.post("/auth/login", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["token_type"], "bearer")
        self.__class__.token = data["access_token"]

    def test_04_get_me(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        response = self.client.get("/auth/me", headers=headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["email"], self.test_email)
        
        # Save user ID and check if admin (since it is the first/test user)
        self.__class__.user_id = data["id"]
        self.__class__.is_admin = (data["role"] == "admin")

    def test_05_create_category(self):
        if not self.is_admin:
            self.skipTest("Requires Admin role")
            
        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {
            "name": "African Fiction",
            "slug": "african-fiction",
            "description": "Fiction novels written by African authors"
        }
        response = self.client.post("/admin/categories", json=payload, headers=headers)
        # 201 on success, 400 if already exists
        self.assertIn(response.status_code, [201, 400])
        if response.status_code == 201:
            data = response.json()
            self.assertEqual(data["slug"], "african-fiction")
            self.__class__.category_id = data["id"]
        else:
            # Fetch existing category ID
            cat = self.db.query(models.Category).filter(models.Category.slug == "african-fiction").first()
            self.__class__.category_id = cat.id

    def test_06_admin_create_book(self):
        if not self.is_admin:
            self.skipTest("Requires Admin role")
            
        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {
            "title": "Things Fall Apart",
            "author": "Chinua Achebe",
            "description": "A classic novel depicting pre-colonial life in Nigeria.",
            "cover_image_url": "https://example.com/things-fall-apart.jpg",
            "file_url": "https://yourdomain.com/files/things-fall-apart.pdf",
            "file_type": "pdf",
            "file_size_kb": 1200,
            "language": "English",
            "publication_year": 1958,
            "publisher": "Heinemann",
            "isbn": "9780385474542",
            "category_id": self.category_id,
            "tags": ["nigerian", "classic", "fiction"],
            "is_public": True
        }
        response = self.client.post("/admin/books", json=payload, headers=headers)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["title"], "Things Fall Apart")
        self.assertEqual(data["author"], "Chinua Achebe")
        self.__class__.book_id = data["id"]

    def test_07_list_books(self):
        response = self.client.get("/books")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(len(data) >= 1)

    def test_08_search_books(self):
        # Test full-text search against the newly created book
        response = self.client.get("/books/search?q=Achebe")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(len(data) >= 1)
        self.assertEqual(data[0]["title"], "Things Fall Apart")

    def test_09_increment_views(self):
        response = self.client.post(f"/books/{self.book_id}/view")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["view_count"], 1)

    def test_10_bookmark_book(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        response = self.client.post(f"/users/bookmarks/{self.book_id}", headers=headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["book_id"], self.book_id)

    def test_11_submit_review(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {
            "rating": 5,
            "comment": "An absolute masterpiece of modern literature."
        }
        response = self.client.post(f"/users/reviews/{self.book_id}", json=payload, headers=headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["rating"], 5)
        self.assertEqual(data["username"], self.test_username)

    def test_12_admin_stats(self):
        if not self.is_admin:
            self.skipTest("Requires Admin role")
            
        headers = {"Authorization": f"Bearer {self.token}"}
        response = self.client.get("/admin/stats", headers=headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["total_books"] >= 1)
        self.assertTrue(data["total_users"] >= 1)

if __name__ == "__main__":
    unittest.main()

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
        cls.test_email = "testuser_profile@example.com"
        cls.test_username = "testuser_profile"
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
        self.assertEqual(response.json(), {"status": "ok"})

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
        self.__class__.user_id = data["id"]
        self.__class__.is_admin = (data["role"] == "admin")

    def test_03_user_login(self):
        payload = {
            "username": self.test_username,
            "password": self.test_password
        }
        response = self.client.post("/auth/login", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("access_token", data)
        self.__class__.token = data["access_token"]

    def test_04_create_category(self):
        if not self.is_admin:
            self.skipTest("Requires Admin role")
            
        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {
            "name": "Test Category",
            "slug": "test-category",
            "description": "For testing purposes"
        }
        response = self.client.post("/admin/categories", json=payload, headers=headers)
        self.assertIn(response.status_code, [201, 400])
        if response.status_code == 201:
            self.__class__.category_id = response.json()["id"]
        else:
            cat = self.db.query(models.Category).filter(models.Category.slug == "test-category").first()
            self.__class__.category_id = cat.id

    def test_05_admin_create_book(self):
        if not self.is_admin:
            self.skipTest("Requires Admin role")
            
        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {
            "title": "Achebe Test Book",
            "author": "Chinua Achebe",
            "category_id": self.category_id,
            "tags": ["test", "tag-filtering"]
        }
        response = self.client.post("/admin/books", json=payload, headers=headers)
        self.assertEqual(response.status_code, 201)
        self.__class__.book_id = response.json()["id"]

    def test_06_list_books_paginated(self):
        response = self.client.get("/books?limit=5")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("items", data)
        self.assertIn("total_count", data)
        self.assertTrue(len(data["items"]) >= 1)

    def test_07_search_books_paginated(self):
        response = self.client.get("/books/search?q=Achebe")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("items", data)
        self.assertTrue(len(data["items"]) >= 1)
        self.assertEqual(data["items"][0]["author"], "Chinua Achebe")

    def test_08_tag_filtering(self):
        response = self.client.get("/books?tag=tag-filtering")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(any("tag-filtering" in b["tags"] for b in data["items"]))

    def test_09_profile_update(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {"username": "updated_testuser"}
        response = self.client.put("/users/me", json=payload, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "updated_testuser")
        # Restore for other tests
        self.client.put("/users/me", json={"username": self.test_username}, headers=headers)

    def test_10_change_password(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {
            "old_password": self.test_password,
            "new_password": "newtestpassword123"
        }
        response = self.client.post("/auth/change-password", json=payload, headers=headers)
        self.assertEqual(response.status_code, 200)

        # Verify new password works
        login_payload = {"username": self.test_username, "password": "newtestpassword123"}
        login_response = self.client.post("/auth/login", json=login_payload)
        self.assertEqual(login_response.status_code, 200)

if __name__ == "__main__":
    unittest.main()

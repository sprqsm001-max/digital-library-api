/*
  African Digital Library - Admin Controller
  Handles catalog management, statistics, category creation, and books deletion.
*/

document.addEventListener('DOMContentLoaded', () => {
  // Check auth
  if (window.API && !window.API.isAdmin()) {
    showToast('Unauthorized access.', 'error');
    setTimeout(() => { location.href = 'index.html'; }, 1500);
    return;
  }

  // Load Dashboard Data
  loadDashboardData();
});

// Switch between admin panels
function switchAdminTab(tabName) {
  document.querySelectorAll('.admin-tabs .admin-tab').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('.admin-tab-content').forEach(p => p.classList.remove('active'));

  let tabButtonId = 'tab-catalog';
  let panelId = 'panel-catalog';

  if (tabName === 'categories') {
    tabButtonId = 'tab-categories';
    panelId = 'panel-categories';
    loadCategoriesTab();
  } else if (tabName === 'users') {
    tabButtonId = 'tab-users';
    panelId = 'panel-users';
    loadUsersTab();
  } else {
    loadCatalogTab();
  }

  const activeBtn = document.getElementById(tabButtonId);
  const activePanel = document.getElementById(panelId);
  if (activeBtn) activeBtn.classList.add('active');
  if (activePanel) activePanel.classList.add('active');
}

// Collapsible Add Book Form
function toggleAddBookForm() {
  const form = document.getElementById('add-book-form-container');
  if (form.style.display === 'none') {
    form.style.display = 'block';
    // Populate categories select dropdown
    populateCategoryDropdown();
  } else {
    form.style.display = 'none';
  }
}

async function populateCategoryDropdown() {
  const select = document.getElementById('book-category');
  try {
    const categories = await API.getCategories();
    select.innerHTML = categories.map(c => `
      <option value="${c.id}">${c.name}</option>
    `).join('');
  } catch (err) {
    select.innerHTML = '<option value="">Failed to load subjects</option>';
  }
}

// Sync slug input when typing category name
function syncCatSlug() {
  const name = document.getElementById('cat-name').value;
  const slug = name.toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '') // Remove invalid chars
    .replace(/\s+/g, '-')         // Replace spaces with -
    .replace(/-+/g, '-');         // Collapse consecutive -
  document.getElementById('cat-slug').value = slug;
}

// Loads statistics
async function loadDashboardData() {
  try {
    const stats = await API.getAdminStats();
    document.getElementById('stat-books').textContent = stats.total_books || 0;
    document.getElementById('stat-users').textContent = stats.total_users || 0;
    document.getElementById('stat-reviews').textContent = stats.total_reviews || 0;
    document.getElementById('stat-downloads').textContent = stats.total_downloads || 0;

    // Trigger catalog load by default
    loadCatalogTab();
  } catch (err) {
    console.error('Failed loading stats', err);
  }
}

// Render Catalog panel
async function loadCatalogTab() {
  const tbody = document.getElementById('catalog-books-tbody');
  tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">Syncing catalog...</td></tr>';

  try {
    const books = await API.getBooks();
    if (books.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">No books in catalog yet.</td></tr>';
      return;
    }

    tbody.innerHTML = books.map(book => `
      <tr>
        <td><img src="${getBookCover(book)}" style="width: 35px; height: 50px; object-fit: cover; border-radius: var(--radius-sm); box-shadow: var(--shadow-sm);"></td>
        <td style="font-weight: 600;">${book.title}</td>
        <td>${book.author}</td>
        <td>${book.category_name || 'Fiction'}</td>
        <td>${book.downloads || 0}</td>
        <td>
          <button onclick="handleDeleteBook(${book.id})" class="btn btn-secondary btn-sm" style="color: var(--accent-coral); padding: 4px 8px; font-size: 0.75rem;">Delete</button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--accent-coral);">Error syncing catalog books.</td></tr>';
  }
}

// Submit Add Book Form
async function submitAddBook(e) {
  e.preventDefault();

  const bookFileInput = document.getElementById('book-file-upload');
  const coverFileInput = document.getElementById('book-cover-upload');

  let file_url = null;
  let file_type = null;
  let file_size_kb = parseInt(document.getElementById('book-size').value) || 0;
  let cover_image_url = document.getElementById('book-cover-url').value.trim() || null;

  try {
    // 1. Handle Book File Upload
    if (bookFileInput.files.length > 0) {
      showToast('Uploading book file...');
      const uploadRes = await API.uploadBookFile(bookFileInput.files[0]);
      file_url = uploadRes.url;
      file_type = uploadRes.file_type;
      file_size_kb = uploadRes.file_size_kb;
    }

    // 2. Handle Cover Image Upload
    if (coverFileInput.files.length > 0) {
      showToast('Uploading cover image...');
      const coverRes = await API.uploadCoverImage(coverFileInput.files[0]);
      cover_image_url = coverRes.url;
    }

    const bookData = {
      title: document.getElementById('book-title').value.trim(),
      author: document.getElementById('book-author').value.trim(),
      category_id: parseInt(document.getElementById('book-category').value),
      language: document.getElementById('book-language').value.trim(),
      publication_year: parseInt(document.getElementById('book-year').value),
      publisher: document.getElementById('book-publisher').value.trim(),
      isbn: document.getElementById('book-isbn').value.trim(),
      file_size_kb: file_size_kb,
      file_url: file_url,
      file_type: file_type,
      cover_image_url: cover_image_url,
      description: document.getElementById('book-desc').value.trim() || null,
      is_public: true
    };

    showToast('Saving book metadata...');
    await API.adminCreateBook(bookData);
    showToast('Book successfully added to library catalog!');

    // Clear form
    document.getElementById('add-book-form').reset();
    toggleAddBookForm();

    // Reload dashboard stats & catalog
    loadDashboardData();
  } catch (err) {
    showToast(err.message || 'Error uploading book catalog metadata', 'error');
  }
}

// Delete book
async function handleDeleteBook(id) {
  if (!confirm('Are you sure you want to permanently delete this book from the library shelves?')) return;

  try {
    showToast('Deleting book...');
    await API.adminDeleteBook(id);
    showToast('Book deleted successfully.');
    loadDashboardData();
  } catch (err) {
    showToast('Error deleting book.', 'error');
  }
}

// Render Categories panel
async function loadCategoriesTab() {
  const tbody = document.getElementById('catalog-categories-tbody');
  tbody.innerHTML = '<tr><td colspan="3" style="text-align: center; color: var(--text-muted);">Syncing categories...</td></tr>';

  try {
    const categories = await API.getCategories();
    tbody.innerHTML = categories.map(cat => `
      <tr>
        <td>${cat.id}</td>
        <td style="font-weight: 600;">${cat.name}</td>
        <td><code>${cat.slug}</code></td>
      </tr>
    `).join('');
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="3" style="text-align: center; color: var(--accent-coral);">Error syncing categories.</td></tr>';
  }
}

// Submit Add Category
async function submitAddCategory(e) {
  e.preventDefault();

  const name = document.getElementById('cat-name').value.trim();
  const slug = document.getElementById('cat-slug').value.trim();

  try {
    showToast('Creating category...');
    await API.adminCreateCategory(name, slug);
    showToast('Category created successfully!');

    document.getElementById('add-category-form').reset();
    loadCategoriesTab();
  } catch (err) {
    showToast('Error creating category. Slug might be already taken.', 'error');
  }
}

// Render Users list panel
async function loadUsersTab() {
  const tbody = document.getElementById('catalog-users-tbody');
  tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">Syncing user accounts...</td></tr>';

  try {
    const users = await API.adminGetUsers();
    tbody.innerHTML = users.map(u => `
      <tr>
        <td>${u.id}</td>
        <td style="font-weight: 600;">${u.username}</td>
        <td>${u.email}</td>
        <td><span class="hero-tag" style="background-color: ${u.role === 'admin' ? 'var(--accent-teal)' : 'var(--text-muted)'}; margin-bottom:0;">${u.role}</span></td>
      </tr>
    `).join('');
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--accent-coral);">Error syncing user records.</td></tr>';
  }
}

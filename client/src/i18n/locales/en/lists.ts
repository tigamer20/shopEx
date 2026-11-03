import type fr from '../fr/lists';

const lists: typeof fr = {
  title: 'My lists',
  history: 'History',
  bookmarks: 'Bookmarks',
  items_count: '{count} item(s)',
  last_used: 'Used on {date}',
  open_hint: 'Opens the list in the editor',
  bookmark_add: 'Bookmark "{name}"',
  bookmark_remove: 'Remove "{name}" from bookmarks',
  delete: 'Delete "{name}"',
  delete_confirm_title: 'Delete this list?',
  delete_confirm_body: '"{name}" will be permanently removed from your history.',
  new_list: 'New list',
  segments: 'List type',
  empty_history_title: 'No lists yet',
  empty_history_body: 'Every search is saved here so you can reuse it.',
  empty_bookmarks_title: 'No bookmarks',
  empty_bookmarks_body: 'Tap the star on a list to turn it into a reusable template.',
};

export default lists;

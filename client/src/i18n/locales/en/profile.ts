import type fr from '../fr/profile';

const profile: typeof fr = {
  title: 'Profile',
  account: 'Account',
  email: 'Email',
  display_name: 'Display name',
  save_name: 'Save name',
  saved: 'Saved',
  preferences: 'Preferences',
  language: 'Language',
  radius: 'Search radius',
  radius_value: '{km} km',
  radius_hint: 'Only stores within this radius are compared.',
  travel_mode: 'Travel mode',
  travel_modes: {
    driving: 'Car',
    walking: 'Walking',
    cycling: 'Bike',
  },
  tutorial: 'Tutorial',
  replay_tutorial: 'Replay the tutorial',
  about: 'About',
  demo_title: 'Demo prices',
  version: 'Version {version}',
  licences: {
    title: 'Licences & sources',
    map_data: 'Stores and maps: © OpenStreetMap contributors, licensed under the ODbL.',
    map_library: 'Map display: Leaflet (BSD-2-Clause licence).',
    icons: 'Icons: Ionicons (MIT licence).',
    brands: 'The product brands shown are fictional. The ShopEx logo is original artwork.',
  },
  profile_unavailable: 'Profile unavailable right now.',
  logout: 'Sign out',
  delete_account: 'Delete my account',
  delete_confirm_title: 'Delete your account?',
  delete_confirm_body: 'Your account and all your lists will be permanently deleted. This cannot be undone.',
};

export default profile;

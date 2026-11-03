// English dictionary: typed against the French one, so a missing or extra key fails to compile.
import type { Dictionary } from '../../types';

import auth from './auth';
import browse from './browse';
import common from './common';
import editor from './editor';
import home from './home';
import itinerary from './itinerary';
import lists from './lists';
import onboarding from './onboarding';
import profile from './profile';
import results from './results';
import search from './search';

const en: Dictionary = {
  common,
  auth,
  onboarding,
  home,
  browse,
  lists,
  profile,
  editor,
  results,
  itinerary,
  search,
};

export default en;

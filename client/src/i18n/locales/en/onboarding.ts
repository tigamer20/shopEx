import type fr from '../fr/onboarding';

const onboarding: typeof fr = {
  start: 'Get started',
  progress: 'Step {current} of {total}',
  slides: {
    welcome: {
      title: 'Welcome to ShopEx',
      body: 'Save on every grocery run by comparing the stores around you.',
    },
    list: {
      title: 'Build your list',
      body: 'Add your items, your favourite brand and the quantity.',
    },
    cheapest: {
      title: 'We find the cheapest',
      body: 'For every item, ShopEx finds the cheapest offer near you.',
    },
    more_options: {
      title: 'More options with "i"',
      body: 'Tap "i" to see 2 other options and swap the offer.',
    },
    route: {
      title: 'The fastest route',
      body: 'Approve your basket: we plan the fastest route between the stores.',
    },
  },
};

export default onboarding;

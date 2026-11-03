import type fr from '../fr/auth';

const auth: typeof fr = {
  login_title: 'Welcome back!',
  login_subtitle: 'Sign in to find your lists.',
  register_title: 'Create an account',
  register_subtitle: 'Start saving on groceries today.',
  email: 'Email',
  email_placeholder: 'name@example.ca',
  password: 'Password',
  password_hint: 'At least {min} characters.',
  show_password: 'Show password',
  hide_password: 'Hide password',
  display_name: 'Display name',
  display_name_placeholder: 'e.g. Sam',
  language: 'Language',
  login_cta: 'Sign in',
  register_cta: 'Create my account',
  no_account: 'No account yet? Sign up',
  have_account: 'Already have an account? Sign in',
  errors: {
    invalid_credentials: 'Invalid email or password.',
    email_taken: 'This email is already in use.',
    email_required: 'Enter your email.',
    email_invalid: 'Enter a valid email.',
    password_required: 'Enter your password.',
    password_too_short: 'The password must be at least {min} characters long.',
    password_too_long: 'The password must be at most {max} characters long.',
    display_name_required: 'Enter a name.',
    display_name_too_long: 'The name must be at most {max} characters long.',
  },
};

export default auth;

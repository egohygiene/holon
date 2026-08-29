export interface Link {
  label: string;
  href: string;
}

export interface Action extends Link {
  tone: "primary" | "secondary";
}

export interface Asset {
  src: string;
  alt: string;
}

export interface Card {
  eyebrow?: string;
  title: string;
  description: string;
  href?: string;
}

export interface SectionCards {
  eyebrow: string;
  title: string;
  description: string;
  items: Card[];
}

export interface LaunchKitContent {
  schema: "holon.launchkit-content/v1";
  identity: {
    wordmark: string;
    logo?: Asset;
  };
  navigation?: Link[];
  announcement?: Link;
  hero: {
    eyebrow: string;
    title: string;
    description: string;
    actions: Action[];
  };
  proof?: {
    title: string;
    items: string[];
  };
  demo?: {
    eyebrow: string;
    title: string;
    description: string;
    asset?: Asset;
    metrics: Array<{ label: string; value: string }>;
  };
  features: SectionCards;
  useCases?: SectionCards;
  code?: {
    eyebrow: string;
    title: string;
    description: string;
    language: string;
    value: string;
  };
  architecture?: SectionCards;
  integrations?: SectionCards;
  trust?: {
    eyebrow: string;
    title: string;
    description: string;
    links: Link[];
  };
  faq?: {
    eyebrow: string;
    title: string;
    description: string;
    items: Array<{ question: string; answer: string }>;
  };
  finalCta?: {
    title: string;
    description: string;
    actions: Action[];
  };
  footer: {
    summary: string;
    groups: Array<{ title: string; links: Link[] }>;
    legal: Link[];
  };
}

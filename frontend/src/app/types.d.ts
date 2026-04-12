import React from 'react';

declare global {
  namespace JSX {
    interface IntrinsicElements {
      [elemName: string]: any;
    }
  }
}

declare module 'react' {
  interface ReactNode {}
}

declare module 'next' {
  export interface Metadata {
    title?: string;
    description?: string;
  }
}

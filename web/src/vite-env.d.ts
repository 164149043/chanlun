/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

declare module 'roughjs/bin/rough.js' {
  const rough: any;
  export default rough;
}

declare module 'roughjs' {
  const rough: any;
  export default rough;
}

declare module '@/assets/styles/variables.scss' {
  const styles: { bgPrimary: string; bgSecondary: string; textPrimary: string; textSecondary: string; colorUp: string; colorDown: string; accentColor: string }
  export default styles;
}

// SCSS 变量需要从 variables.scss 导入，light-theme.scss 不需要额外声明

import { createApp } from 'vue'
import { createPinia } from 'pinia' // 如果你装了 pinia，没装可以去掉这行
import App from './App.vue'
import router from './router' // <--- 关键：导入你刚才写的路由配置

import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue' // 导入图标

const app = createApp(App)

// 1. 注册图标 (为了让 Sidebar 里的图标正常显示)
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// 2. 使用插件
app.use(createPinia()) // 如果没装 pinia，删掉这行
app.use(router)        // <--- 🚨 核心修复：必须在这里注册 router
app.use(ElementPlus)

// 3. 最后挂载
app.mount('#app')

import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Backtest from '../views/Backtest.vue'
import Ma120Backtest from '../views/Ma120Backtest.vue'
import DrawboardView from '../views/DrawboardView.vue'
import GridBacktestView from '../views/GridBacktestView.vue'
import EtfFlowView from '../views/EtfFlowView.vue'
import ValuationView from '../views/ValuationView.vue'
import EventDashboardView from '../views/EventDashboardView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: Home },
    { path: '/backtest', name: 'backtest', component: Backtest },
    { path: '/ma120', name: 'ma120', component: Ma120Backtest },
    { path: '/drawboard', name: 'drawboard', component: DrawboardView },
    { path: '/grid', name: 'grid', component: GridBacktestView },
    { path: '/etf-flow', name: 'etf-flow', component: EtfFlowView },
    { path: '/valuation', name: 'valuation', component: ValuationView },
    { path: '/event', name: 'event', component: EventDashboardView },
  ],
})

export default router

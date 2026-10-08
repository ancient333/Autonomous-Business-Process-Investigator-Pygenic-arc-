import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./qa',testMatch:'**/*.playwright.ts',use:{baseURL:'http://localhost:8080',viewport:{width:1440,height:900}},timeout:30000});

import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const data = resolve('..', 'data', 'synthetic_documents');
async function register(page) {
  await page.goto('/register');
  const name = `browser_${Date.now()}_${Math.floor(Math.random()*1000)}`;
  await page.getByLabel('Username', {exact:true}).fill(name);
  await page.getByLabel('Email address').fill(`${name}@example.com`);
  await page.getByLabel('Password', {exact:true}).fill('Browser-demo-password-42');
  await page.getByRole('button', {name:'Create account',exact:true}).click();
  await expect(page.getByRole('heading', {name:`Hello, ${name}.`})).toBeVisible();
}
async function fillProfile(page) {
  await page.getByRole('link', {name:'My profile',exact:true}).click();
  await page.getByLabel('Full name', {exact:true}).fill('Asha Rao');
  await page.getByLabel('Date of birth').fill('1988-04-12');
  await page.getByLabel('Annual family income (INR)').fill('120000');
  await page.getByLabel('Bank account available').selectOption('true');
  await page.getByLabel('State / union territory').fill('Telangana');
  await page.getByRole('button', {name:'Save profile'}).click();
  await expect(page.getByRole('status')).toContainText('Profile saved');
}
test.beforeEach(async ({page}) => {
  page.errors = [];
  page.on('pageerror', error => page.errors.push(error.message));
});
test.afterEach(async ({page}) => { expect(page.errors).toEqual([]); });

test('registration, incomplete profile, correction and explained recommendation', async ({page}) => {
  await register(page);
  await page.goto('/schemes/demo-family-support');
  await expect(page.getByText('Potentially eligible',{exact:true})).toBeVisible();
  await fillProfile(page);
  await page.getByRole('link',{name:'For you',exact:true}).click();
  await expect(page.getByRole('link',{name:'Demo Family Support',exact:true})).toBeVisible();
  await page.getByRole('link',{name:'Demo Family Support',exact:true}).click();
  await page.getByRole('button',{name:'Check eligibility'}).click();
  await expect(page.getByText('Eligible',{exact:true})).toBeVisible();
  await expect(page.getByText(/Your value: 120000/)).toBeVisible();
  await page.screenshot({path:'../artifacts/test-results/scheme-desktop.png',fullPage:true});
  await page.getByRole('link',{name:'Overview',exact:true}).click();
  await page.screenshot({path:'../artifacts/test-results/dashboard-desktop.png',fullPage:true});
});

test('real PDF upload, mismatch correction, readiness, export and deletion', async ({page}) => {
  await register(page); await fillProfile(page);
  await page.getByRole('link',{name:'My documents',exact:true}).click();
  for (const file of ['asha-identity.pdf','meera-income-mismatch.pdf','asha-residence.pdf']) {
    await page.getByLabel('Choose a document').setInputFiles(resolve(data,file));
    await page.getByRole('button',{name:'Upload document',exact:true}).click();
    await expect(page.getByRole('status').filter({ hasText: 'Uploaded' })).toContainText(`Uploaded ${file}`);
  }
  await page.goto('/schemes/demo-family-support');
  await expect(page.getByText('Incomplete',{exact:true})).toBeVisible();
  await page.getByRole('link',{name:'My documents',exact:true}).click();
  await page.getByRole('button',{name:/meera-income-mismatch.pdf Income certificate/}).click();
  await page.getByText('Correct or add information',{exact:true}).click();
  await page.getByLabel('Full name',{exact:true}).fill('Asha Rao');
  await page.getByLabel('Annual family income',{exact:true}).fill('120000');
  await page.getByLabel('I confirm these synthetic document details.').check();
  await page.getByRole('button',{name:'Save corrections'}).click();
  await expect(page.getByText('User-confirmed corrections',{exact:true})).toBeVisible();
  await page.goto('/schemes/demo-family-support');
  await expect(page.getByText('Ready',{exact:true})).toBeVisible();
  const download = page.waitForEvent('download');
  await page.getByRole('button',{name:'Download summary'}).click();
  const exported = await download;
  expect(exported.suggestedFilename()).toContain('preparation.html');
  await page.getByRole('link',{name:'My documents',exact:true}).click();
  await page.getByRole('button',{name:'Delete asha-identity.pdf'}).click();
  await page.getByRole('button',{name:'Confirm delete'}).click();
  await page.goto('/schemes/demo-family-support');
  await expect(page.getByText('Incomplete',{exact:true})).toBeVisible();
});

test('real local cited retrieval, unsupported question and personal eligibility', async ({page}) => {
  await register(page); await fillProfile(page);
  await page.goto('/chat?scheme=demo-family-support');
  await page.getByLabel('Your question').fill('What is the income limit for Demo Family Support?');
  await page.getByRole('button',{name:'Send question'}).click();
  await expect(page.locator('.message.assistant').first()).toContainText('200,000',{timeout:60000});
  await expect(page.locator('.message.assistant').first()).toContainText('Local source-based assistance');
  await page.locator('.citations summary').first().click();
  await expect(page.locator('.message.assistant .citations').first()).toContainText('Chunk:');
  await page.getByLabel('Your question').fill('What will my income tax refund be next week?');
  await page.getByRole('button',{name:'Send question'}).click();
  await expect(page.locator('.message.assistant').nth(1)).toContainText('Insufficient information');
  await page.getByLabel('Your question').fill('Am I eligible for this scheme?');
  await page.getByRole('button',{name:'Send question'}).click();
  await expect(page.locator('.message.assistant').nth(2)).toContainText('Deterministic profile result');
  await page.screenshot({path:'../artifacts/test-results/chat-desktop.png',fullPage:true});
});

test('recoverable profile failure preserves input and narrow screen stays usable', async ({page}) => {
  await register(page);
  await page.getByRole('link',{name:'My profile',exact:true}).click();
  await page.getByLabel('Full name',{exact:true}).fill('Unsaved Example');
  await page.route('**/api/v1/profile', async route => route.request().method() === 'PATCH' ? route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Temporary test outage'})}) : route.continue());
  await page.getByRole('button',{name:'Save profile'}).click();
  await expect(page.getByRole('alert')).toContainText('Temporary test outage');
  await expect(page.getByLabel('Full name',{exact:true})).toHaveValue('Unsaved Example');
  await page.unroute('**/api/v1/profile');
  await page.setViewportSize({width:390,height:844});
  await page.goto('/schemes');
  await expect(page.getByRole('heading',{name:'Support for every next chapter.'})).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({path:'../artifacts/test-results/catalog-mobile.png',fullPage:true});
});

test('admin edits and archives are reflected in citizen catalog', async ({page}) => {
  const admin = JSON.parse(readFileSync(resolve('..','runtime','browser-admin.json'),'utf8'));
  await page.goto('/login');
  await page.getByLabel('Username',{exact:true}).fill(admin.username);
  await page.getByLabel('Password',{exact:true}).fill(admin.password);
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await page.getByRole('link',{name:'Administration',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Installation analytics'})).toBeVisible();
  await page.getByRole('button',{name:'New scheme'}).click();
  const editor = page.getByLabel('Scheme JSON');
  const value = JSON.parse(await editor.inputValue());
  value.id = `browser-demo-${Date.now()}`;
  value.name = 'Browser demonstration scheme';
  await editor.fill(JSON.stringify(value));
  await page.getByRole('button',{name:'Validate and save'}).click();
  const row = page.getByRole('row').filter({hasText:value.id});
  await row.getByRole('button',{name:'Publish',exact:true}).click();
  await expect(row).toContainText('Published');
  await page.goto(`/schemes/${value.id}`);
  await expect(page.getByRole('heading',{name:value.name})).toBeVisible();
  await page.getByRole('link',{name:'Administration',exact:true}).click();
  await row.getByRole('button',{name:'Edit',exact:true}).click();
  const edited = JSON.parse(await editor.inputValue());
  edited.name = 'Browser demonstration scheme — updated';
  edited.benefits = 'Updated fictional education benefit for the browser verification.';
  await editor.fill(JSON.stringify(edited));
  await page.getByRole('button',{name:'Validate and save'}).click();
  await expect(row).toContainText(edited.name);
  await row.getByRole('button',{name:'Publish',exact:true}).click();
  await expect(row).toContainText('Published');
  await page.goto(`/schemes/${value.id}`);
  await expect(page.getByRole('heading',{name:edited.name})).toBeVisible();
  await expect(page.getByText(edited.benefits,{exact:true})).toBeVisible();
  await page.getByRole('link',{name:'Administration',exact:true}).click();
  await row.getByRole('button',{name:'Archive',exact:true}).click();
  await page.goto(`/schemes/${value.id}`);
  await expect(page.getByRole('alert').first()).toContainText('Scheme not found');
});


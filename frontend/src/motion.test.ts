import {describe,it,expect} from 'vitest';
import {portalValues,shouldThrow} from './motion';
describe('portal calculations (not browser layout verification)',()=>{
 it('reverses with scroll and grows while tightening',()=>{const a=portalValues(0,900),b=portalValues(700,900);expect(b.panel).toBeGreaterThan(a.panel);expect(b.scale).toBeGreaterThan(a.scale);expect(b.tracking).toBeLessThan(a.tracking);expect(portalValues(0,900)).toEqual(a)});
 it('calculates over 100px panel travel for 1440px viewport',()=>{expect(portalValues(700,900).panel/100*(1440*.505)).toBeGreaterThan(100)});
 it('clamps and opens with reduced motion',()=>{expect(portalValues(-100,900).p).toBe(0);expect(portalValues(0,900,true).p).toBe(1);expect(portalValues(5000,900).p).toBe(1)});
 it('requires more than ten percent deck drag',()=>{expect(shouldThrow(40,400)).toBe(false);expect(shouldThrow(-41,400)).toBe(true)})
});

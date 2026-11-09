import brand from '../../../common/brand_assets.json';

export function BrandLogo({ compact = false }: { compact?: boolean }) {
  return <img className={compact ? 'brand-logo brand-logo--compact' : 'brand-logo'}
    src={brand.logo.path} alt={brand.logo.alt} />;
}

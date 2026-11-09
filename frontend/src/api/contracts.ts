export type Temperature = 'HOT' | 'COLD';
export type ServiceType = 'DINE_IN' | 'TAKEOUT';
export interface MenuOption { id: string; label: string; price_delta_krw: number; }
export interface MenuOptionGroup { id: string; label: string; max_selections: number; choices: MenuOption[]; }
export interface ApiMenu {
  menu_id: string;
  name: string;
  categories: string[];
  price_krw: number;
  available_temperatures: Temperature[];
  variants: { temperature: Temperature; image_url: string; option_groups?: MenuOptionGroup[] }[];
  image_url: string;
  is_available: boolean;
  display_order: number;
  is_featured: boolean;
}
export interface MenusResponse { menus: ApiMenu[]; }
interface OrderSelection {
  menu_id: string;
  temperature: Temperature;
  service_type: ServiceType;
}
export interface CreateOrderRequest extends OrderSelection {
  request_id: string;
  option_ids?: string[];
}
export interface OrderResponse extends OrderSelection {
  // DB BIGINT 주문번호는 정밀도를 유지하기 위해 문자열로 전달한다.
  order_id: string;
  order_number: string;
  menu_name: string;
  quantity: 1;
  total_price_krw: number;
  selected_options?: MenuOption[];
  created_at: string;
}
export interface KioskApi {
  getMenus(signal?: AbortSignal): Promise<MenusResponse>;
  createOrder(request: CreateOrderRequest, signal?: AbortSignal): Promise<OrderResponse>;
}

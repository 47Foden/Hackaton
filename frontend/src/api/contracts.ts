export type Temperature = 'HOT' | 'COLD';
export type ServiceType = 'DINE_IN' | 'TAKEOUT';
export interface ApiMenu {
  menu_id: string;
  name: string;
  categories: string[];
  price_krw: number;
  available_temperatures: Temperature[];
  variants: { temperature: Temperature; image_url: string }[];
  image_url: string;
  is_available: boolean;
  display_order: number;
  is_featured: boolean;
}
export interface MenusResponse { menus: ApiMenu[]; }
export interface CreateOrderRequest {
  menu_id: string;
  temperature: Temperature;
  service_type: ServiceType;
}
export interface OrderResponse extends CreateOrderRequest {
  // DB BIGINT 주문번호는 정밀도를 유지하기 위해 문자열로 전달한다.
  order_id: string;
  order_number: string;
  menu_name: string;
  quantity: 1;
  total_price_krw: number;
  created_at: string;
}
export interface KioskApi {
  getMenus(signal?: AbortSignal): Promise<MenusResponse>;
  createOrder(request: CreateOrderRequest, signal?: AbortSignal): Promise<OrderResponse>;
}

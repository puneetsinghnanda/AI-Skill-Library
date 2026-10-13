import { NavLink } from 'react-router-dom';

export function NavBar() {
  return (
    <header className="nav">
      <strong>Order Tracker</strong>
      <nav aria-label="Main">
        <NavLink to="/orders" end>
          Order history
        </NavLink>{' '}
        <NavLink to="/orders/new">New order</NavLink> <NavLink to="/products">Products</NavLink>
      </nav>
    </header>
  );
}
